import calendar
import base64
import csv
import io
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from uuid import uuid4
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .analytics import calculate_kpis, evaluate_alerts, forecast_cash
from .database import Base, SessionLocal, engine, get_db
from .models import (Activity, Alert, AlertRule, Attachment, Budget, Category, Client, Invoice,
                     InvoiceItem, Payment, Quote, QuoteItem, RecurringRule, Setting, Transaction,
                     User, WorkSession)
from .schemas import (ActivityIn, AlertRuleIn, AlertStatusIn, BudgetIn, CategoryIn, ClientIn,
                      LoginIn, PaymentIn, QuoteIn, RecurringRuleIn, RegisterIn, SettingsIn, TokenOut,
                      TransactionIn, WorkSessionIn)
from .security import create_access_token, get_current_user, hash_password, verify_password
from .seed import initialize_workspace

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("finpilot")
ATTACHMENT_UPLOAD_ROOT = Path(__file__).resolve().parents[1] / "data" / "uploads"
DEVELOPER_SIGNATURE = "Conçu et développé par Jérémie GASBEOGO"

DEFAULT_ALERT_RULES = {
    "client_concentration": {"threshold_pct": 40},
    "category_spike": {"threshold_pct": 30},
    "late_invoice": {},
    "cash_forecast": {"threshold_months": 2},
    "target_lag": {},
    "recurring_review": {"min_monthly_xof": 25_000},
    "recurring_increase": {"threshold_pct": 20},
    "activity_margin_decline": {"drop_pct": 15, "min_previous_revenue_xof": 100_000},
    "activity_opportunity": {"min_revenue_xof": 100_000},
    "savings_opportunity": {"min_savings_xof": 10_000},
}


def _ensure_default_alert_rules(db: Session, user_id: str):
    existing = {row.rule_type for row in db.query(AlertRule).filter_by(user_id=user_id).all()}
    for rule_type, parameters in DEFAULT_ALERT_RULES.items():
        if rule_type not in existing:
            db.add(AlertRule(user_id=user_id, rule_type=rule_type, parameters=parameters, is_active=True))
    db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for user_id, in db.query(User.id).all():
            _ensure_default_alert_rules(db, user_id)
    yield


app = FastAPI(title="FinPilot API", version="1.0.0", description="Pilotage financier d'activité indépendante", lifespan=lifespan)
configured_origins = os.getenv("FINPILOT_CORS_ORIGINS", "")
allowed_origins = [origin.strip().rstrip("/") for origin in configured_origins.split(",") if origin.strip()]
if not allowed_origins:
    allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_request, exc):
    log.info("Integrity error: %s", exc.__class__.__name__)
    return Response(content=json.dumps({"detail": "Conflit de données ou référence invalide."}, ensure_ascii=False), status_code=409, media_type="application/json")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "FinPilot API"}


@app.post("/api/auth/register", response_model=TokenOut, status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(func.lower(User.email) == payload.email).first():
        raise HTTPException(409, "Cette adresse e-mail est déjà utilisée")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    initialize_workspace(db, user.id)
    db.commit()
    _ensure_default_alert_rules(db, user.id)
    return {"access_token": create_access_token(user.id)}


@app.post("/api/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(User.email) == payload.email.strip().lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "E-mail ou mot de passe incorrect")
    return {"access_token": create_access_token(user.id)}


@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email}


def _owned(db: Session, model, item_id: str, user_id: str, message="Élément introuvable"):
    row = db.query(model).filter(model.id == item_id, model.user_id == user_id).first()
    if row is None:
        raise HTTPException(404, message)
    return row


def _check_reference(db, model, item_id, user_id, label):
    if item_id and db.query(model.id).filter(model.id == item_id, model.user_id == user_id).first() is None:
        raise HTTPException(422, f"{label} invalide")


def _settings(db: Session, user_id: str):
    row = db.query(Setting).filter_by(user_id=user_id, key="preferences").first()
    return row.value if row else {"currency": "XOF", "fx_rate": 1, "locale": "fr-FR", "theme": "light", "monthly_target_xof": 0, "annual_target_xof": 0, "business_name": "Jérémie GASBEOGO"}


def _period(year: int, month: int | None = None, quarter: int | None = None):
    if month:
        if month < 1 or month > 12:
            raise HTTPException(422, "Mois invalide")
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    if quarter:
        if quarter < 1 or quarter > 4:
            raise HTTPException(422, "Trimestre invalide")
        first_month = (quarter - 1) * 3 + 1
        last_month = first_month + 2
        return date(year, first_month, 1), date(year, last_month, calendar.monthrange(year, last_month)[1])
    return date(year, 1, 1), date(year, 12, 31)


def _date_shift(start: date, end: date):
    days = (end - start).days + 1
    return start - timedelta(days=days), start - timedelta(days=1)


def _all_financial(db: Session, user_id: str):
    return (db.query(Transaction).filter_by(user_id=user_id).all(),
            db.query(Invoice).filter_by(user_id=user_id).all(),
            db.query(Payment).filter_by(user_id=user_id).all(),
            db.query(Category).filter_by(user_id=user_id).all())


def _recompute_alerts(db: Session, user_id: str, kpis: dict, txs, invoices, payments, settings,
                      recurring_rules=(), activity_names=None):
    rules = db.query(AlertRule).filter_by(user_id=user_id).all()
    candidates = evaluate_alerts(txs, invoices, payments, kpis, rules, settings.get("monthly_target_xof", 0),
                                 recurring_rules=recurring_rules, activity_names=activity_names)
    candidate_keys = {item["dedupe_key"] for item in candidates}
    for existing_active in db.query(Alert).filter_by(user_id=user_id, status="active").all():
        if existing_active.dedupe_key not in candidate_keys:
            existing_active.status = "resolved"
    for item in candidates:
        row = db.query(Alert).filter_by(user_id=user_id, dedupe_key=item["dedupe_key"]).order_by(Alert.generated_at.desc()).first()
        if row is not None:
            if row.status in ("active", "acknowledged"):
                row.title = item["title"]
                row.severity = item["severity"]
                row.explanation = item["explanation"]
                row.recommendation = item["recommendation"]
                row.details = item["details"]
            continue
        rule = next((r for r in rules if r.rule_type == item["rule_type"]), None)
        db.add(Alert(user_id=user_id, rule_id=rule.id if rule else None, severity=item["severity"], status="active",
                     title=item["title"], explanation=item["explanation"], recommendation=item["recommendation"],
                     details=item["details"], dedupe_key=item["dedupe_key"]))
    db.commit()


@app.get("/api/activities")
def list_activities(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Activity).filter_by(user_id=user.id, is_active=True).order_by(Activity.name).all()


@app.post("/api/activities", status_code=201)
def create_activity(payload: ActivityIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = Activity(user_id=user.id, **payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item


@app.get("/api/categories")
def list_categories(kind: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Category).filter_by(user_id=user.id, is_active=True)
    if kind in ("income", "expense"):
        query = query.filter_by(kind=kind)
    return query.order_by(Category.name).all()


@app.post("/api/categories", status_code=201)
def create_category(payload: CategoryIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = Category(user_id=user.id, **payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item


@app.get("/api/clients")
def list_clients(search: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Client).filter_by(user_id=user.id, is_active=True)
    if search:
        q = q.filter(Client.name.ilike(f"%{search.strip()}%"))
    clients = q.order_by(Client.name).all()
    txs = db.query(Transaction).filter_by(user_id=user.id, kind="income", status="received").all()
    invoices = db.query(Invoice).filter_by(user_id=user.id).all()
    payments = db.query(Payment).filter_by(user_id=user.id).all()
    paid = {}
    for p in payments:
        paid[p.invoice_id] = paid.get(p.invoice_id, 0) + p.amount_xof
    billed_by_client = {}
    payment_days_by_client = {}
    for invoice in invoices:
        billed_by_client[invoice.client_id] = billed_by_client.get(invoice.client_id, 0) + invoice.total_xof
        for payment in payments:
            if payment.invoice_id == invoice.id and payment.paid_at >= invoice.issue_date:
                days, amount = payment_days_by_client.get(invoice.client_id, (0, 0))
                payment_days_by_client[invoice.client_id] = (days + max(0, (payment.paid_at - invoice.issue_date).days) * payment.amount_xof, amount + payment.amount_xof)
    revenue_months = {}
    for transaction in txs:
        revenue_months.setdefault(transaction.client_id, set()).add(transaction.transaction_date.strftime("%Y-%m"))
    result = []
    for client in clients:
        revenue = sum(t.amount_xof for t in txs if t.client_id == client.id)
        balance = sum(max(0, i.total_xof - paid.get(i.id, 0)) for i in invoices if i.client_id == client.id and i.status != "cancelled")
        result.append({"id": client.id, "name": client.name, "first_name": client.first_name, "last_name": client.last_name, "email": client.email, "phone": client.phone, "payment_terms_days": client.payment_terms_days,
                       "reliability_score": client.reliability_score, "notes": client.notes, "revenue_xof": revenue,
                       "billed_xof": billed_by_client.get(client.id, 0), "receivables_xof": balance,
                       "average_payment_days": round(payment_days_by_client.get(client.id, (0,0))[0] / payment_days_by_client.get(client.id, (0,0))[1], 1) if payment_days_by_client.get(client.id, (0,0))[1] else None,
                       "recurring_rate_pct": min(100, round(100 * len(revenue_months.get(client.id, ())) / max(1, len({t.transaction_date.strftime('%Y-%m') for t in txs})), 1))})
    result.sort(key=lambda x: x["revenue_xof"], reverse=True)
    total = sum(r["revenue_xof"] for r in result)
    cumulative = 0
    for row in result:
        cumulative += row["revenue_xof"]
        row["segment"] = "A" if total and cumulative - row["revenue_xof"] < total * .8 else ("B" if total and cumulative - row["revenue_xof"] < total * .95 else "C")
    return result


@app.post("/api/clients", status_code=201)
def create_client(payload: ClientIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = Client(user_id=user.id, **payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item


@app.put("/api/clients/{client_id}")
def update_client(client_id: str, payload: ClientIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = _owned(db, Client, client_id, user.id)
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    db.commit(); db.refresh(item)
    return item


@app.delete("/api/clients/{client_id}", status_code=204)
def archive_client(client_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = _owned(db, Client, client_id, user.id)
    item.is_active = False
    db.commit()


@app.get("/api/clients/{client_id}")
def client_detail(client_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    client = _owned(db, Client, client_id, user.id)
    transactions = db.query(Transaction).filter_by(user_id=user.id, client_id=client_id).order_by(Transaction.transaction_date.desc()).all()
    invoices = db.query(Invoice).filter_by(user_id=user.id, client_id=client_id).all()
    payments = db.query(Payment).filter_by(user_id=user.id).all()
    paid = {i.id: sum(p.amount_xof for p in payments if p.invoice_id == i.id) for i in invoices}
    return {"client": client, "transactions": transactions, "revenue_xof": sum(t.amount_xof for t in transactions if t.kind == "income" and t.status == "received"),
            "expenses_xof": sum(t.amount_xof for t in transactions if t.kind == "expense" and t.status == "received"),
            "receivables_xof": sum(max(0, i.total_xof - paid[i.id]) for i in invoices if i.status != "cancelled"), "invoices": invoices}


@app.get("/api/transactions")
def list_transactions(kind: str | None = None, status: str | None = None, year: int | None = None, month: int | None = None,
                      quarter: int | None = None, activity_id: str | None = None, client_id: str | None = None, search: str = "",
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Transaction).filter_by(user_id=user.id)
    if kind in ("income", "expense"): q = q.filter_by(kind=kind)
    if status in ("received", "pending", "overdue"): q = q.filter_by(status=status)
    if year:
        start, end = _period(year, month, quarter)
        q = q.filter(Transaction.transaction_date.between(start, end))
    if activity_id: q = q.filter_by(activity_id=activity_id)
    if client_id: q = q.filter_by(client_id=client_id)
    if search: q = q.filter(Transaction.description.ilike(f"%{search.strip()}%"))
    rows = q.order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc()).limit(1000).all()
    changed = False
    for row in rows:
        if row.status == "pending" and row.due_date and row.due_date < date.today():
            row.status = "overdue"; changed = True
    if changed: db.commit()
    return rows


@app.post("/api/transactions", status_code=201)
def create_transaction(payload: TransactionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = payload.model_dump()
    for model, field, label in ((Activity, "activity_id", "Activité"), (Client, "client_id", "Client"), (Category, "category_id", "Catégorie")):
        _check_reference(db, model, data[field], user.id, label)
    if data["category_id"] and db.get(Category, data["category_id"]).kind != data["kind"]:
        raise HTTPException(422, "La catégorie ne correspond pas au type de flux")
    item = Transaction(user_id=user.id, **data)
    db.add(item); db.commit(); db.refresh(item)
    return item


@app.put("/api/transactions/{transaction_id}")
def update_transaction(transaction_id: str, payload: TransactionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = _owned(db, Transaction, transaction_id, user.id)
    if item.source == "invoice_payment": raise HTTPException(409, "Cette transaction provient d'un règlement de facture")
    data = payload.model_dump()
    for model, field, label in ((Activity, "activity_id", "Activité"), (Client, "client_id", "Client"), (Category, "category_id", "Catégorie")):
        _check_reference(db, model, data[field], user.id, label)
    if data["category_id"] and db.get(Category, data["category_id"]).kind != data["kind"]:
        raise HTTPException(422, "La catégorie ne correspond pas au type de flux")
    for key, value in data.items(): setattr(item, key, value)
    db.commit(); db.refresh(item)
    return item


@app.delete("/api/transactions/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = _owned(db, Transaction, transaction_id, user.id)
    if item.source == "invoice_payment": raise HTTPException(409, "Supprimez le règlement depuis la facture associée")
    db.delete(item); db.commit()


@app.post("/api/transactions/{transaction_id}/attachments", status_code=201)
async def upload_attachment(transaction_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    transaction = _owned(db, Transaction, transaction_id, user.id)
    contents = await file.read(10 * 1024 * 1024 + 1)
    if len(contents) > 10 * 1024 * 1024: raise HTTPException(413, "Fichier trop volumineux (10 Mo max)")
    if not contents: raise HTTPException(422, "Le fichier est vide")
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(file.filename or "piece-jointe").name)[:180]
    # Stocker le fichier dans la base rend les reçus persistants sur un hébergeur éphémère.
    row = Attachment(user_id=user.id, transaction_id=transaction.id, filename=safe_name,
                     storage_path=f"database://attachments/{uuid4().hex}",
                     mime_type=file.content_type or "application/octet-stream", content=contents)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "filename": row.filename, "mime_type": row.mime_type, "url": f"/api/attachments/{row.id}"}


@app.get("/api/attachments/{attachment_id}")
def download_attachment(attachment_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _owned(db, Attachment, attachment_id, user.id)
    if row.content is not None:
        # Le nom a été normalisé à l'import ; il peut être envoyé sans échappement arbitraire.
        return Response(content=row.content, media_type=row.mime_type,
                        headers={"Content-Disposition": f'attachment; filename="{row.filename}"'})
    # Lecture de compatibilité pour les pièces jointes créées par les anciennes versions.
    path = Path(row.storage_path).resolve()
    if not path.is_file(): raise HTTPException(404, "Fichier indisponible")
    return FileResponse(path, media_type=row.mime_type, filename=row.filename)


@app.get("/api/transactions/{transaction_id}/attachments")
def list_attachments(transaction_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _owned(db, Transaction, transaction_id, user.id)
    rows = db.query(Attachment).filter_by(user_id=user.id, transaction_id=transaction_id).order_by(Attachment.created_at.desc()).all()
    # Ne jamais sérialiser les octets du fichier dans la liste JSON.
    return [{"id": row.id, "filename": row.filename, "mime_type": row.mime_type,
             "created_at": row.created_at, "url": f"/api/attachments/{row.id}"} for row in rows]


@app.get("/api/profitability")
def profitability(year: int = Query(default_factory=lambda: date.today().year), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    start, end = _period(year)
    txs = db.query(Transaction).filter(Transaction.user_id == user.id, Transaction.status == "received", Transaction.transaction_date.between(start, end)).all()
    activities = {a.id: a.name for a in db.query(Activity).filter_by(user_id=user.id).all()}
    clients = {c.id: c.name for c in db.query(Client).filter_by(user_id=user.id).all()}
    categories = {c.id: c for c in db.query(Category).filter_by(user_id=user.id).all()}
    hours = db.query(WorkSession).filter(WorkSession.user_id == user.id, WorkSession.started_at.between(datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time()))).all()
    by_activity = {}
    by_client = {}
    for t in txs:
        activity = t.activity_id or "unassigned"
        client = t.client_id or "unassigned"
        for group, key in ((by_activity, activity), (by_client, client)):
            group.setdefault(key, {"revenue_xof": 0, "expenses_xof": 0, "direct_cost_xof": 0})
            if t.kind == "income": group[key]["revenue_xof"] += t.amount_xof
            else:
                group[key]["expenses_xof"] += t.amount_xof
                if categories.get(t.category_id) and categories[t.category_id].cost_type == "direct": group[key]["direct_cost_xof"] += t.amount_xof
    session_hours = {}
    for h in hours: session_hours[h.activity_id or "unassigned"] = session_hours.get(h.activity_id or "unassigned", 0) + float(h.hours)
    activity_rows = []
    for key, values in by_activity.items():
        values.update({"activity_id": key, "name": activities.get(key, "Non affecté"), "profit_xof": values["revenue_xof"] - values["expenses_xof"], "gross_margin_pct": round(100 * (values["revenue_xof"] - values["direct_cost_xof"]) / values["revenue_xof"], 1) if values["revenue_xof"] else 0, "hours": round(session_hours.get(key, 0), 1), "revenue_per_hour_xof": round(values["revenue_xof"] / session_hours[key]) if session_hours.get(key) else None})
        activity_rows.append(values)
    client_rows = []
    for key, values in by_client.items():
        values.update({"client_id": key, "name": clients.get(key, "Sans client"), "margin_xof": values["revenue_xof"] - values["expenses_xof"], "margin_pct": round(100 * (values["revenue_xof"] - values["expenses_xof"]) / values["revenue_xof"], 1) if values["revenue_xof"] else 0})
        client_rows.append(values)
    activity_rows.sort(key=lambda x: x["profit_xof"], reverse=True); client_rows.sort(key=lambda x: x["margin_xof"], reverse=True)
    service_rows = {}
    for h in hours:
        key = h.service_type or "Non classé"
        service_rows.setdefault(key, {"hours": 0, "revenue_xof": 0})
        service_rows[key]["hours"] += float(h.hours); service_rows[key]["revenue_xof"] += h.revenue_xof
    for row in service_rows.values(): row["revenue_per_hour_xof"] = round(row["revenue_xof"] / row["hours"]) if row["hours"] else 0
    total_income = sum(t.amount_xof for t in txs if t.kind == "income")
    total_expenses = sum(t.amount_xof for t in txs if t.kind == "expense")
    fixed = sum(t.amount_xof for t in txs if t.kind == "expense" and categories.get(t.category_id) and categories[t.category_id].cost_type == "fixed")
    variable = sum(t.amount_xof for t in txs if t.kind == "expense" and (not categories.get(t.category_id) or categories[t.category_id].cost_type != "fixed"))
    contribution_rate = (total_income - variable) / total_income if total_income else 0
    return {"year": year, "activities": activity_rows, "clients": client_rows, "services": [{"service_type": k, **v} for k,v in service_rows.items()],
            "fixed_costs_xof": fixed, "variable_costs_xof": variable, "break_even_xof": round(fixed / contribution_rate) if contribution_rate > 0 else 0,
            "revenue_xof": total_income, "expenses_xof": total_expenses, "profit_xof": total_income-total_expenses}


@app.post("/api/work-sessions", status_code=201)
def create_work_session(payload: WorkSessionIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    for model, field, label in ((Activity, "activity_id", "Activité"), (Client, "client_id", "Client")):
        _check_reference(db, model, getattr(payload, field), user.id, label)
    session = WorkSession(user_id=user.id, **payload.model_dump())
    db.add(session); db.commit(); db.refresh(session)
    return session


@app.post("/api/recurring-rules", status_code=201)
def create_recurring_rule(payload: RecurringRuleIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.activity_id: _check_reference(db, Activity, payload.activity_id, user.id, "Activité")
    if payload.category_id: _check_reference(db, Category, payload.category_id, user.id, "Catégorie")
    rule = RecurringRule(user_id=user.id, **payload.model_dump())
    db.add(rule); db.commit(); db.refresh(rule)
    return rule


@app.get("/api/recurring-rules")
def list_recurring_rules(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(RecurringRule).filter_by(user_id=user.id).order_by(RecurringRule.next_run).all()


@app.post("/api/recurring-rules/run")
def run_recurring_rules(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today(); due = db.query(RecurringRule).filter(RecurringRule.user_id == user.id, RecurringRule.is_active.is_(True), RecurringRule.next_run <= today).all()
    created = 0
    for rule in due:
        run_date = rule.next_run
        while run_date <= today:
            ref = f"recurring:{rule.id}:{run_date.isoformat()}"
            if not db.query(Transaction.id).filter_by(user_id=user.id, reference=ref).first():
                db.add(Transaction(user_id=user.id, activity_id=rule.activity_id, category_id=rule.category_id, kind=rule.kind, amount_xof=rule.amount_xof, transaction_date=run_date, due_date=run_date, status="pending", description=rule.description, reference=ref, source="recurring")); created += 1
            if rule.frequency == "weekly":
                run_date += timedelta(days=7)
            else:
                offset = 1 if rule.frequency == "monthly" else (3 if rule.frequency == "quarterly" else 12)
                absolute_month = run_date.year * 12 + run_date.month - 1 + offset
                next_year, month0 = divmod(absolute_month, 12)
                next_month = month0 + 1
                run_date = date(next_year, next_month, min(run_date.day, calendar.monthrange(next_year, next_month)[1]))
        rule.next_run = run_date
    db.commit()
    return {"created": created, "rules_processed": len(due)}


@app.get("/api/dashboard")
def dashboard(year: int = Query(default_factory=lambda: date.today().year), month: Optional[int] = None, quarter: Optional[int] = None,
              activity_id: str | None = None, client_id: str | None = None,
              db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    start, end = _period(year, month, quarter)
    prev_start, prev_end = _date_shift(start, end)
    txs, invoices, payments, categories = _all_financial(db, user.id)
    all_txs = txs
    all_invoices = invoices
    all_payments = payments
    quotes = db.query(Quote).filter_by(user_id=user.id).all()
    if activity_id:
        txs = [t for t in txs if t.activity_id == activity_id]
        invoices = [i for i in invoices if i.activity_id == activity_id]
    if client_id:
        txs = [t for t in txs if t.client_id == client_id]
        invoices = [i for i in invoices if i.client_id == client_id]
    invoice_ids = {i.id for i in invoices}
    payments = [p for p in payments if p.invoice_id in invoice_ids]
    settings = _settings(db, user.id)
    cash = sum(t.amount_xof if t.kind == "income" else -t.amount_xof for t in txs if t.status == "received" and t.transaction_date <= end)
    kpis = calculate_kpis(txs, invoices, payments, quotes, categories, start, end, prev_start, prev_end, cash)
    activities = {a.id: a.name for a in db.query(Activity).filter_by(user_id=user.id).all()}
    clients = {c.id: c.name for c in db.query(Client).filter_by(user_id=user.id).all()}
    for row in kpis["activities"]: row["activity_name"] = activities.get(row["activity_id"], "Non affecté")
    for row in kpis["top_clients"]: row["client_name"] = clients.get(row["client_id"], "Sans client")
    today = date.today()
    alert_start = date(today.year, today.month, 1)
    alert_cash = sum(t.amount_xof if t.kind == "income" else -t.amount_xof for t in all_txs
                     if t.status == "received" and t.transaction_date <= today)
    alert_kpis = calculate_kpis(all_txs, all_invoices, all_payments, quotes, categories,
                                alert_start, today, cash_balance=alert_cash)
    recurring_rules = db.query(RecurringRule).filter_by(user_id=user.id).all()
    _recompute_alerts(db, user.id, alert_kpis, all_txs, all_invoices, all_payments, settings,
                      recurring_rules, activities)
    alerts = db.query(Alert).filter_by(user_id=user.id, status="active").order_by(Alert.generated_at.desc()).limit(6).all()
    recent_query = db.query(Transaction).filter(Transaction.user_id == user.id, Transaction.transaction_date.between(start, end))
    if activity_id: recent_query = recent_query.filter_by(activity_id=activity_id)
    if client_id: recent_query = recent_query.filter_by(client_id=client_id)
    recent = recent_query.order_by(Transaction.transaction_date.desc()).limit(8).all()
    budget_rows = db.query(Budget).filter(Budget.user_id == user.id, Budget.period_start <= end, Budget.period_end >= start).all()
    expense_actual = {}
    for t in txs:
        if t.kind == "expense" and t.status == "received": expense_actual[t.category_id] = expense_actual.get(t.category_id, 0) + t.amount_xof
    budget_totals = {}
    for b in budget_rows: budget_totals[b.category_id] = budget_totals.get(b.category_id, 0) + b.amount_xof
    budgets = [{"category_id": category_id, "category_name": next((c.name for c in categories if c.id == category_id), "Catégorie"), "budget_xof": amount, "actual_xof": expense_actual.get(category_id, 0)} for category_id, amount in budget_totals.items()]
    return {"period": {"start": start, "end": end}, "kpis": kpis, "alerts": alerts, "recent_transactions": recent,
            "budgets": budgets, "settings": settings, "activities": list(activities.items()), "clients": list(clients.items())}


@app.post("/api/quotes", status_code=201)
def create_quote(payload: QuoteIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    client = _owned(db, Client, payload.client_id, user.id, "Client introuvable")
    if payload.activity_id: _check_reference(db, Activity, payload.activity_id, user.id, "Activité")
    if payload.valid_until < payload.issue_date: raise HTTPException(422, "La validité doit être postérieure à la date du devis")
    year = payload.issue_date.year
    count = db.query(Quote).filter(Quote.user_id == user.id, Quote.number.like(f"DEV-{year}-%")).count() + 1
    quote = Quote(user_id=user.id, client_id=client.id, activity_id=payload.activity_id, number=f"DEV-{year}-{count:03d}", status="draft", issue_date=payload.issue_date, valid_until=payload.valid_until, notes=payload.notes)
    subtotal = tax = 0
    for row in payload.items:
        gross = round(row.quantity * row.unit_price_xof)
        net = max(0, gross - row.discount_xof)
        item_tax = round(net * row.tax_rate / 100)
        subtotal += net; tax += item_tax
        quote.items.append(QuoteItem(**row.model_dump()))
    quote.subtotal_xof = subtotal; quote.tax_xof = tax; quote.total_xof = subtotal + tax
    db.add(quote); db.commit(); db.refresh(quote)
    return quote


@app.put("/api/quotes/{quote_id}")
def update_quote(quote_id: str, payload: QuoteIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    quote = _owned(db, Quote, quote_id, user.id)
    if quote.status != "draft": raise HTTPException(409, "Seul un brouillon peut être modifié")
    _owned(db, Client, payload.client_id, user.id, "Client introuvable")
    if payload.activity_id: _check_reference(db, Activity, payload.activity_id, user.id, "Activité")
    if payload.valid_until < payload.issue_date: raise HTTPException(422, "La validité doit être postérieure à la date du devis")
    quote.client_id = payload.client_id; quote.activity_id = payload.activity_id
    quote.issue_date = payload.issue_date; quote.valid_until = payload.valid_until; quote.notes = payload.notes
    quote.items.clear()
    subtotal = tax = 0
    for row in payload.items:
        gross = round(row.quantity * row.unit_price_xof)
        net = max(0, gross - row.discount_xof)
        item_tax = round(net * row.tax_rate / 100)
        subtotal += net; tax += item_tax
        quote.items.append(QuoteItem(**row.model_dump()))
    quote.subtotal_xof = subtotal; quote.tax_xof = tax; quote.total_xof = subtotal + tax
    db.commit(); db.refresh(quote)
    return quote


@app.delete("/api/quotes/{quote_id}", status_code=204)
def delete_quote(quote_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    quote = _owned(db, Quote, quote_id, user.id)
    if quote.status != "draft": raise HTTPException(409, "Seul un brouillon peut être supprimé")
    if db.query(Invoice.id).filter_by(quote_id=quote.id).first(): raise HTTPException(409, "Ce devis est lié à une facture")
    db.delete(quote); db.commit()

@app.get("/api/quotes")
def list_quotes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Quote).filter_by(user_id=user.id).order_by(Quote.issue_date.desc()).all()


@app.patch("/api/quotes/{quote_id}/status")
def update_quote_status(quote_id: str, status: str = Query(pattern="^(draft|sent|accepted|rejected|expired)$"), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    quote = _owned(db, Quote, quote_id, user.id)
    if status == "accepted" and quote.status != "accepted":
        quote.accepted_at = date.today()
    quote.status = status; db.commit(); db.refresh(quote)
    return quote


@app.post("/api/quotes/{quote_id}/convert")
def convert_quote(quote_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    quote = _owned(db, Quote, quote_id, user.id)
    if quote.status != "accepted": raise HTTPException(409, "Seul un devis accepté peut être converti")
    existing = db.query(Invoice).filter_by(user_id=user.id, quote_id=quote.id).first()
    if existing: return existing
    year = date.today().year
    count = db.query(Invoice).filter(Invoice.user_id == user.id, Invoice.number.like(f"FAC-{year}-%")).count() + 1
    invoice = Invoice(user_id=user.id, client_id=quote.client_id, activity_id=quote.activity_id, quote_id=quote.id,
                      number=f"FAC-{year}-{count:03d}", status="issued", issue_date=date.today(),
                      due_date=date.today() + timedelta(days=30), subtotal_xof=quote.subtotal_xof,
                      tax_xof=quote.tax_xof, total_xof=quote.total_xof, notes=quote.notes)
    for row in quote.items:
        invoice.items.append(InvoiceItem(designation=row.designation, quantity=row.quantity, unit_price_xof=row.unit_price_xof, discount_xof=row.discount_xof, tax_rate=row.tax_rate))
    db.add(invoice); db.commit(); db.refresh(invoice)
    return invoice


def _document_pdf(title, number, client, issue_date, due_date, items, total, settings, notes=""):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet()
    story = [Paragraph(escape(settings.get("business_name", "FinPilot")), styles["Title"]), Paragraph(escape(title), styles["Heading2"]),
             Paragraph(f"N° {escape(str(number))} · Émis le {issue_date} · Client : {escape(client.name)}", styles["Normal"]),
             Paragraph(f"Valide jusqu'au {due_date}" if title == "DEVIS" else f"Échéance : {due_date}", styles["Normal"]), Spacer(1, 18)]
    data = [["Désignation", "Qté", "Prix unitaire", "Remise", "Montant"]]
    for item in items:
        amount = max(0, round(float(item.quantity) * item.unit_price_xof) - item.discount_xof)
        data.append([escape(item.designation), str(item.quantity), f"{item.unit_price_xof:,}", f"{item.discount_xof:,}", f"{amount:,}"])
    data.extend([["", "", "", "Total", f"{total:,} FCFA"]])
    table = Table(data, repeatRows=1, colWidths=[220, 45, 80, 60, 90])
    table.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0), colors.HexColor("#222222")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.4,colors.HexColor("#dddddd")),("ALIGN",(1,1),(-1,-1),"RIGHT"),("BACKGROUND",(0,-1),(-1,-1),colors.HexColor("#f4f4f4")),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
    story += [table, Spacer(1, 14)]
    if notes: story.append(Paragraph(escape(notes), styles["Normal"]))
    if settings.get("legal_mentions"): story += [Spacer(1, 20), Paragraph(escape(settings["legal_mentions"]), styles["Italic"])]
    story += [Spacer(1, 18), Paragraph(escape(DEVELOPER_SIGNATURE), styles["Italic"])]
    doc.build(story)
    output.seek(0)
    return output.getvalue()


@app.get("/api/quotes/{quote_id}/pdf")
def quote_pdf(quote_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    quote = _owned(db, Quote, quote_id, user.id)
    client = _owned(db, Client, quote.client_id, user.id)
    content = _document_pdf("DEVIS", quote.number, client, quote.issue_date, quote.valid_until, quote.items, quote.total_xof, _settings(db, user.id), quote.notes)
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{quote.number}.pdf"'})


@app.get("/api/invoices")
def list_invoices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Invoice).filter_by(user_id=user.id).order_by(Invoice.issue_date.desc()).all()
    payments = db.query(Payment).filter_by(user_id=user.id).all()
    names = {c.id: c.name for c in db.query(Client).filter_by(user_id=user.id).all()}
    result = []
    for inv in rows:
        amount_paid = sum(p.amount_xof for p in payments if p.invoice_id == inv.id)
        result.append({"id": inv.id, "number": inv.number, "client_id": inv.client_id, "client_name": names.get(inv.client_id, ""), "issue_date": inv.issue_date, "due_date": inv.due_date, "total_xof": inv.total_xof, "paid_xof": amount_paid, "balance_xof": max(0, inv.total_xof-amount_paid), "status": "paid" if amount_paid >= inv.total_xof else ("overdue" if inv.due_date < date.today() else inv.status)})
    return result


@app.get("/api/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invoice = _owned(db, Invoice, invoice_id, user.id)
    client = _owned(db, Client, invoice.client_id, user.id)
    content = _document_pdf("FACTURE", invoice.number, client, invoice.issue_date, invoice.due_date, invoice.items, invoice.total_xof, _settings(db, user.id), invoice.notes)
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{invoice.number}.pdf"'})


@app.get("/api/pricing/recommendation")
def recommend_price(cost_xof: int = Query(gt=0), target_margin_pct: float = Query(default=35, gt=0, lt=100), hours: float | None = Query(default=None, gt=0), hourly_floor_xof: int = Query(default=0, ge=0)):
    price_for_margin = round(cost_xof / (1 - target_margin_pct / 100))
    price_for_hourly_floor = round(hours * hourly_floor_xof) if hours and hourly_floor_xof else 0
    suggested = max(price_for_margin, price_for_hourly_floor)
    return {"cost_xof": cost_xof, "target_margin_pct": target_margin_pct, "suggested_price_xof": suggested,
            "estimated_margin_xof": suggested - cost_xof, "estimated_margin_pct": round(100 * (suggested - cost_xof) / suggested, 1),
            "hourly_floor_price_xof": price_for_hourly_floor}


@app.post("/api/invoices/{invoice_id}/payments", status_code=201)
def create_payment(invoice_id: str, payload: PaymentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invoice = _owned(db, Invoice, invoice_id, user.id)
    if invoice.status == "cancelled": raise HTTPException(409, "Facture annulée")
    paid = sum(p.amount_xof for p in db.query(Payment).filter_by(invoice_id=invoice_id).all())
    if paid + payload.amount_xof > invoice.total_xof: raise HTTPException(422, "Le paiement dépasse le solde de la facture")
    category = db.query(Category).filter_by(user_id=user.id, kind="income").first()
    tx = Transaction(user_id=user.id, activity_id=invoice.activity_id, client_id=invoice.client_id,
                     category_id=category.id if category else None, kind="income", amount_xof=payload.amount_xof,
                     transaction_date=payload.paid_at, status="received", payment_method=payload.payment_method,
                     description=f"Règlement {invoice.number}", source="invoice_payment")
    db.add(tx); db.flush()
    payment = Payment(user_id=user.id, invoice_id=invoice.id, transaction_id=tx.id, amount_xof=payload.amount_xof,
                      paid_at=payload.paid_at, payment_method=payload.payment_method)
    db.add(payment)
    if paid + payload.amount_xof == invoice.total_xof: invoice.status = "paid"
    db.commit(); db.refresh(payment)
    return payment


@app.delete("/api/payments/{payment_id}", status_code=204)
def delete_payment(payment_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    payment = _owned(db, Payment, payment_id, user.id)
    invoice = _owned(db, Invoice, payment.invoice_id, user.id)
    if payment.transaction_id:
        transaction = db.query(Transaction).filter_by(id=payment.transaction_id, user_id=user.id).first()
        if transaction: db.delete(transaction)
    db.delete(payment)
    db.flush()
    remaining = sum(row.amount_xof for row in db.query(Payment).filter_by(invoice_id=invoice.id).all())
    invoice.status = "paid" if remaining >= invoice.total_xof else ("partially_paid" if remaining else "issued")
    db.commit()


@app.patch("/api/invoices/{invoice_id}/status")
def update_invoice_status(invoice_id: str, status: str = Query(pattern="^(issued|cancelled)$"), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invoice = _owned(db, Invoice, invoice_id, user.id)
    if status == "cancelled" and db.query(Payment.id).filter_by(invoice_id=invoice.id).first():
        raise HTTPException(409, "Une facture avec paiements ne peut pas être annulée")
    invoice.status = status; db.commit(); db.refresh(invoice)
    return invoice


@app.post("/api/budgets", status_code=201)
def create_budget(payload: BudgetIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.period_end < payload.period_start: raise HTTPException(422, "Période de budget invalide")
    _check_reference(db, Category, payload.category_id, user.id, "Catégorie")
    if payload.activity_id: _check_reference(db, Activity, payload.activity_id, user.id, "Activité")
    item = Budget(user_id=user.id, **payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item


@app.get("/api/budgets")
def list_budgets(year: int = Query(default_factory=lambda: date.today().year), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Budget).filter(Budget.user_id == user.id, Budget.period_start <= date(year,12,31), Budget.period_end >= date(year,1,1)).all()


@app.get("/api/alerts")
def list_alerts(status: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(Alert).filter_by(user_id=user.id)
    if status: query = query.filter_by(status=status)
    return query.order_by(Alert.generated_at.desc()).limit(100).all()


@app.post("/api/alert-rules", status_code=201)
def create_alert_rule(payload: AlertRuleIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    existing = db.query(AlertRule).filter_by(user_id=user.id, rule_type=payload.rule_type).first()
    if existing:
        existing.parameters = payload.parameters
        existing.is_active = payload.is_active
        db.commit(); db.refresh(existing)
        return existing
    rule = AlertRule(user_id=user.id, **payload.model_dump())
    db.add(rule); db.commit(); db.refresh(rule)
    return rule


@app.get("/api/alert-rules")
def list_alert_rules(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(AlertRule).filter_by(user_id=user.id).order_by(AlertRule.rule_type).all()


@app.patch("/api/alert-rules/{rule_id}")
def update_alert_rule(rule_id: str, payload: AlertRuleIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rule = _owned(db, AlertRule, rule_id, user.id)
    duplicate = db.query(AlertRule).filter(AlertRule.user_id == user.id, AlertRule.rule_type == payload.rule_type, AlertRule.id != rule.id).first()
    if duplicate: raise HTTPException(409, "Une règle de ce type existe déjà pour cet espace")
    rule.rule_type = payload.rule_type; rule.parameters = payload.parameters; rule.is_active = payload.is_active
    db.commit(); db.refresh(rule)
    return rule


@app.patch("/api/alerts/{alert_id}")
def update_alert(alert_id: str, payload: AlertStatusIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    alert = _owned(db, Alert, alert_id, user.id)
    alert.status = payload.status; db.commit(); db.refresh(alert)
    return alert


@app.get("/api/forecast")
def get_forecast(scenario: str = Query(default="realistic", pattern="^(optimistic|realistic|pessimistic)$"), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    txs = db.query(Transaction).filter_by(user_id=user.id, status="received").all()
    settings = _settings(db, user.id)
    now = date.today()
    start, _ = _period(now.year, now.month)
    cash = sum(t.amount_xof if t.kind == "income" else -t.amount_xof for t in txs if t.transaction_date <= now)
    history = []
    for offset in range(17, -1, -1):
        refmonth = now.month - offset
        year = now.year + (refmonth-1)//12
        month = (refmonth-1)%12 + 1
        left = date(year, month, 1); right = date(year, month, calendar.monthrange(year, month)[1])
        selected = [t for t in txs if left <= t.transaction_date <= right]
        history.append({"month": left.strftime("%Y-%m"), "income_xof": sum(t.amount_xof for t in selected if t.kind=="income"), "expenses_xof": sum(t.amount_xof for t in selected if t.kind=="expense"), "partial": left <= now <= right})
    forecast = forecast_cash(history, cash, 3, scenario)
    return {"scenario": scenario, "opening_cash_xof": cash, "forecast": forecast, "history": history[-6:],
            "method": "Moyenne mobile des 3 derniers mois; ajustement saisonnier borné si un an d’historique est disponible."}


@app.get("/api/settings")
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _settings(db, user.id)


@app.put("/api/settings")
def update_settings(payload: SettingsIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if payload.currency not in ("XOF", "EUR", "USD", "GBP", "CAD"): raise HTTPException(422, "Devise non prise en charge")
    row = db.query(Setting).filter_by(user_id=user.id, key="preferences").first()
    value = payload.model_dump()
    if row: row.value = value
    else: db.add(Setting(user_id=user.id, key="preferences", value=value))
    db.commit(); return value


@app.get("/api/settings/backup")
def backup_data(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    models = [Activity, Client, Category, Transaction, Quote, QuoteItem, Invoice, InvoiceItem, Payment, Budget, AlertRule, Alert, Setting, RecurringRule, Attachment, WorkSession]
    data = {"format": "finpilot-user-backup-v2", "user_id": user.id, "created_at": datetime.now(timezone.utc).isoformat(), "tables": {}}
    quote_ids = [row[0] for row in db.query(Quote.id).filter_by(user_id=user.id).all()]
    invoice_ids = [row[0] for row in db.query(Invoice.id).filter_by(user_id=user.id).all()]
    attachment_size = 0
    for model in models:
        query = db.query(model)
        if model is QuoteItem:
            query = query.filter(QuoteItem.quote_id.in_(quote_ids)) if quote_ids else query.filter(False)
        elif model is InvoiceItem:
            query = query.filter(InvoiceItem.invoice_id.in_(invoice_ids)) if invoice_ids else query.filter(False)
        else:
            query = query.filter_by(user_id=user.id)
        records = query.all()
        rows = []
        for record in records:
            row = {}
            for column in model.__table__.columns:
                if model is Attachment and column.name == "content":
                    continue
                value = getattr(record, column.name)
                if isinstance(value, (date, datetime)):
                    row[column.name] = value.isoformat()
                elif isinstance(value, Decimal):
                    row[column.name] = float(value)
                else:
                    row[column.name] = value
            if model is Attachment:
                source = Path(record.storage_path)
                if record.content is not None:
                    attachment_bytes = record.content
                elif source.is_file():
                    attachment_bytes = source.read_bytes()
                else:
                    attachment_bytes = None
                if attachment_bytes is not None:
                    attachment_size += len(attachment_bytes)
                    if attachment_size > 12 * 1024 * 1024:
                        raise HTTPException(413, "Les pièces jointes dépassent 12 Mo; exportez-les séparément avant la sauvegarde.")
                    row["content_base64"] = base64.b64encode(attachment_bytes).decode("ascii")
                else:
                    row["content_base64"] = ""
                row["storage_path"] = ""
            rows.append(row)
        data["tables"][model.__tablename__] = rows
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    if len(body) > 20 * 1024 * 1024:
        raise HTTPException(413, "La sauvegarde dépasse la limite de 20 Mo.")
    return Response(body, media_type="application/json", headers={"Content-Disposition": "attachment; filename=finpilot-backup.json"})


@app.post("/api/settings/restore")
async def restore_data(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    contents = await file.read(20 * 1024 * 1024 + 1)
    if len(contents) > 20 * 1024 * 1024: raise HTTPException(413, "Sauvegarde trop volumineuse (20 Mo max)")
    try:
        data = json.loads(contents.decode("utf-8"))
        if data.get("format") not in ("finpilot-user-backup-v1", "finpilot-user-backup-v2") or data.get("user_id") != user.id:
            raise ValueError("Sauvegarde incompatible avec ce compte")
        tables = data["tables"]
    except Exception as exc:
        raise HTTPException(400, f"Fichier de sauvegarde invalide : {exc}")
    model_map = {model.__tablename__: model for model in [Activity, Client, Category, Transaction, Quote, QuoteItem, Invoice, InvoiceItem, Payment, Budget, AlertRule, Alert, Setting, RecurringRule, Attachment, WorkSession]}
    quote_ids = [row[0] for row in db.query(Quote.id).filter_by(user_id=user.id).all()]
    invoice_ids = [row[0] for row in db.query(Invoice.id).filter_by(user_id=user.id).all()]
    transaction_ids = {row.get("id") for row in tables.get("transactions", [])
                       if row.get("user_id", user.id) == user.id}
    uploads_folder = (ATTACHMENT_UPLOAD_ROOT / user.id).resolve()
    old_attachment_paths = [Path(row.storage_path).resolve() for row in db.query(Attachment).filter_by(user_id=user.id).all()]
    new_attachment_paths = []
    delete_order = [Payment, InvoiceItem, Invoice, QuoteItem, Quote, Attachment, Transaction, Budget, Alert, AlertRule, RecurringRule, WorkSession, Setting, Category, Activity, Client]
    try:
        for model in delete_order:
            if model is QuoteItem:
                if quote_ids: db.query(model).filter(QuoteItem.quote_id.in_(quote_ids)).delete(synchronize_session=False)
            elif model is InvoiceItem:
                if invoice_ids: db.query(model).filter(InvoiceItem.invoice_id.in_(invoice_ids)).delete(synchronize_session=False)
            else:
                db.query(model).filter_by(user_id=user.id).delete(synchronize_session=False)
        restore_order = [Activity, Client, Category, Transaction, Quote, QuoteItem, Invoice, InvoiceItem, Payment, Budget, AlertRule, Alert, Setting, RecurringRule, Attachment, WorkSession]
        restored_quote_ids = {row.get("id") for row in tables.get("quotes", [])}
        restored_invoice_ids = {row.get("id") for row in tables.get("invoices", [])}
        for model in restore_order:
            rows = tables.get(model.__tablename__, [])
            records = []
            for row in rows:
                if row.get("user_id", user.id) != user.id: continue
                if model is QuoteItem and row.get("quote_id") not in restored_quote_ids: continue
                if model is InvoiceItem and row.get("invoice_id") not in restored_invoice_ids: continue
                if model is Attachment and row.get("transaction_id") not in transaction_ids: continue
                clean = dict(row)
                attachment_content = clean.pop("content_base64", "") if model is Attachment else ""
                for column in model.__table__.columns:
                    value = clean.get(column.name)
                    if value is not None and isinstance(value, str):
                        try:
                            pytype = column.type.python_type
                            if pytype is date: clean[column.name] = date.fromisoformat(value)
                            elif pytype is datetime: clean[column.name] = datetime.fromisoformat(value)
                        except (NotImplementedError, ValueError, TypeError): pass
                if model is Attachment:
                    if attachment_content:
                        raw_attachment = base64.b64decode(attachment_content, validate=True)
                        if not raw_attachment or len(raw_attachment) > 10 * 1024 * 1024:
                            raise ValueError("Pièce jointe invalide ou supérieure à 10 Mo")
                        clean["content"] = raw_attachment
                        clean["storage_path"] = f"database://attachments/{clean.get('id') or uuid4().hex}"
                    else:
                        legacy_path = Path(clean.get("storage_path") or "").resolve()
                        if not legacy_path.is_relative_to(uploads_folder) or not legacy_path.is_file():
                            continue
                        clean["storage_path"] = str(legacy_path)
                records.append(model(**clean))
            db.add_all(records)
            db.flush()
        # Une sauvegarde plus ancienne peut ne pas contenir le marqueur de seed.
        # Le créer ici évite que le prochain démarrage nettoie des données restaurées.
        if not db.query(Setting.id).filter_by(user_id=user.id, key="workspace_seed_version").first():
            db.add(Setting(user_id=user.id, key="workspace_seed_version", value={"version": 2}))
        db.commit()
        for old_path in old_attachment_paths:
            if old_path.is_relative_to(uploads_folder) and old_path not in new_attachment_paths and old_path.is_file():
                old_path.unlink(missing_ok=True)
    except Exception as exc:
        db.rollback(); log.exception("Restore failed")
        for path in new_attachment_paths:
            path.unlink(missing_ok=True)
        raise HTTPException(400, f"Restauration annulée : {exc}")
    return {"restored": True, "tables": len(model_map)}


@app.post("/api/transactions/import-csv")
async def import_transactions(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not (file.filename or "").lower().endswith(".csv"): raise HTTPException(415, "Veuillez fournir un fichier CSV")
    try:
        raw = await file.read(20 * 1024 * 1024 + 1)
        if len(raw) > 20 * 1024 * 1024: raise HTTPException(413, "Fichier trop volumineux (20 Mo max)")
        content = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        required = {"kind", "amount_xof", "transaction_date", "description"}
        if not required.issubset(set(reader.fieldnames or [])): raise ValueError("Colonnes requises : kind, amount_xof, transaction_date, description")
        created = duplicates = errors = 0
        row_errors = []
        for line, row in enumerate(reader, start=2):
            try:
                payload = TransactionIn(**{key: row.get(key) or None for key in TransactionIn.model_fields if key in row and row.get(key) not in (None, "")})
                for model, field, label in ((Activity, "activity_id", "Activité"), (Client, "client_id", "Client"), (Category, "category_id", "Catégorie")):
                    _check_reference(db, model, getattr(payload, field), user.id, label)
                if payload.category_id and db.get(Category, payload.category_id).kind != payload.kind:
                    raise ValueError("La catégorie ne correspond pas au type de flux")
                duplicate = db.query(Transaction).filter_by(user_id=user.id, kind=payload.kind, amount_xof=payload.amount_xof, transaction_date=payload.transaction_date, description=payload.description).first()
                if duplicate: duplicates += 1; continue
                db.add(Transaction(user_id=user.id, **payload.model_dump())); created += 1
            except Exception as exc:
                errors += 1; row_errors.append({"line": line, "error": str(exc)[:180]})
        db.commit()
        return {"created": created, "duplicates": duplicates, "errors": errors, "row_errors": row_errors[:20]}
    except UnicodeDecodeError: raise HTTPException(400, "Le CSV doit être encodé en UTF-8")
    except ValueError as exc: raise HTTPException(422, str(exc))


@app.get("/api/transactions/export-csv")
def export_transactions(year: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Transaction).filter_by(user_id=user.id)
    if year: q = q.filter(func.strftime("%Y", Transaction.transaction_date) == str(year))
    rows = q.order_by(Transaction.transaction_date).all()
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["kind", "amount_xof", "transaction_date", "due_date", "status", "payment_method", "activity_id", "client_id", "category_id", "description", "reference", "income_type", f"signature ({DEVELOPER_SIGNATURE})"])
    for row in rows:
        values = [row.kind, row.amount_xof, row.transaction_date, row.due_date or "", row.status, row.payment_method or "", row.activity_id or "", row.client_id or "", row.category_id or "", row.description, row.reference or "", row.income_type or "", DEVELOPER_SIGNATURE]
        writer.writerow([("'" + value) if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value for value in values])
    return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=finpilot-transactions.csv"})


@app.get("/api/reports/monthly.xlsx")
def monthly_report_xlsx(year: int = Query(default_factory=lambda: date.today().year), month: int = Query(default_factory=lambda: date.today().month), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    start, end = _period(year, month)
    txs, invoices, payments, categories = _all_financial(db, user.id)
    quotes = db.query(Quote).filter_by(user_id=user.id).all()
    kpis = calculate_kpis(txs, invoices, payments, quotes, categories, start, end)
    wb = Workbook(); ws = wb.active; ws.title = "Synthèse mensuelle"
    month_names = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    ws.append([f"FinPilot — Bilan {month_names[month]} {year}"])
    ws.append(["Indicateur", "Valeur (FCFA / %)" ])
    for key, label in [("revenue_xof", "CA encaissé"), ("billed_revenue_xof", "CA facturé"), ("expenses_xof", "Dépenses réglées"), ("net_profit_xof", "Résultat net de trésorerie"), ("net_margin_pct", "Marge nette (%)"), ("receivables_xof", "Créances"), ("savings_rate_pct", "Taux d'épargne (%)"), ("dso_days", "DSO (jours)"), ("quote_acceptance_days", "Délai moyen d'acceptation (jours)"), ("client_concentration_pct", "Concentration premier client (%)")]: ws.append([label, kpis.get(key, 0)])
    ws.append([]); ws.append(["Alertes actives"])
    def safe_cell(value):
        return "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value
    for alert in db.query(Alert).filter_by(user_id=user.id, status="active").all():
        ws.append([safe_cell(alert.severity), safe_cell(alert.title), safe_cell(alert.explanation)])
    ws.freeze_panes = "A3"; ws.column_dimensions["A"].width = 42; ws.column_dimensions["B"].width = 28; ws.column_dimensions["C"].width = 76
    for cell in ws[1]: cell.font = Font(bold=True, size=16, color="FFFFFF"); cell.fill = PatternFill("solid", fgColor="252525")
    for cell in ws[2]: cell.font = Font(bold=True, color="FFFFFF"); cell.fill = PatternFill("solid", fgColor="E8763A")
    for row in ws.iter_rows():
        for cell in row: cell.alignment = Alignment(vertical="center", wrap_text=True)
    output = io.BytesIO(); wb.save(output); output.seek(0)
    return Response(output.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=finpilot-bilan-{year}-{month:02d}.xlsx"})


@app.get("/api/reports/monthly.pdf")
def monthly_report_pdf(year: int = Query(default_factory=lambda: date.today().year), month: int = Query(default_factory=lambda: date.today().month), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    start, end = _period(year, month); txs, invoices, payments, categories = _all_financial(db, user.id)
    quotes = db.query(Quote).filter_by(user_id=user.id).all()
    kpis = calculate_kpis(txs, invoices, payments, quotes, categories, start, end)
    buff = io.BytesIO(); doc = SimpleDocTemplate(buff, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    styles = getSampleStyleSheet(); story = [Paragraph(f"FinPilot — Bilan financier {month:02d}/{year}", styles["Title"]), Spacer(1, 18)]
    acceptance = "—" if kpis["quote_acceptance_days"] is None else f"{kpis['quote_acceptance_days']} jours"
    rows = [["Indicateur", "Valeur"], ["CA encaissé", f"{kpis['revenue_xof']:,} FCFA"], ["CA facturé", f"{kpis['billed_revenue_xof']:,} FCFA"], ["Dépenses réglées", f"{kpis['expenses_xof']:,} FCFA"], ["Résultat net", f"{kpis['net_profit_xof']:,} FCFA"], ["Marge nette", f"{kpis['net_margin_pct']} %"], ["Créances", f"{kpis['receivables_xof']:,} FCFA"], ["DSO", f"{kpis['dso_days']} jours"], ["Délai moyen d'acceptation", acceptance]]
    table = Table(rows, colWidths=[260, 220]); table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#252525")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.5,colors.HexColor("#dddddd")),("ALIGN",(1,1),(-1,-1),"RIGHT"),("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),9)]))
    story += [table, Spacer(1, 18), Paragraph("Alertes et recommandations", styles["Heading2"])]
    active_alerts = db.query(Alert).filter_by(user_id=user.id, status="active").all()
    if active_alerts:
        for alert in active_alerts[:8]:
            story.append(Paragraph(f"<b>{escape(alert.title)}</b> — {escape(alert.explanation)} Action : {escape(alert.recommendation)}", styles["BodyText"]))
    else: story.append(Paragraph("Aucune alerte active sur la période.", styles["BodyText"]))
    story += [Spacer(1, 18), Paragraph(escape(DEVELOPER_SIGNATURE), styles["Italic"])]
    doc.build(story); buff.seek(0)
    return Response(buff.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=finpilot-bilan-{year}-{month:02d}.pdf"})


@app.get("/")
def root():
    return {"name": "FinPilot", "api": "/api", "docs": "/docs"}
