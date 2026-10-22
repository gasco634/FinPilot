from datetime import date, datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def uid() -> str:
    return str(uuid4())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_activity_user_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(7), default="#1E4DD8")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (UniqueConstraint("user_id", "email", name="uq_client_user_email"), CheckConstraint("reliability_score IS NULL OR (reliability_score >= 1 AND reliability_score <= 5)", name="ck_client_reliability"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    first_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)
    reliability_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", "kind", name="uq_category_user_name_kind"), CheckConstraint("kind IN ('income','expense')", name="ck_category_kind"), CheckConstraint("cost_type IS NULL OR cost_type IN ('fixed','variable','direct')", name="ck_category_cost_type"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(12))
    cost_type: Mapped[str | None] = mapped_column(String(12), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_user_date", "user_id", "transaction_date"),
        Index("ix_transactions_user_kind_status", "user_id", "kind", "status"),
        CheckConstraint("kind IN ('income','expense')", name="ck_transaction_kind"),
        CheckConstraint("status IN ('received','pending','overdue')", name="ck_transaction_status"),
        CheckConstraint("amount_xof > 0", name="ck_transaction_amount_positive"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("activities.id", ondelete="SET NULL"), nullable=True, index=True)
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(12))
    income_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    amount_xof: Mapped[int] = mapped_column(Integer)
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="received")
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str] = mapped_column(String(240), default="")
    reference: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Quote(Base):
    __tablename__ = "quotes"
    __table_args__ = (UniqueConstraint("user_id", "number", name="uq_quote_user_number"), CheckConstraint("status IN ('draft','sent','accepted','rejected','expired')", name="ck_quote_status"), CheckConstraint("total_xof >= 0", name="ck_quote_total_nonnegative"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="RESTRICT"), index=True)
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("activities.id", ondelete="SET NULL"), nullable=True)
    number: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    issue_date: Mapped[date] = mapped_column(Date)
    accepted_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date] = mapped_column(Date)
    subtotal_xof: Mapped[int] = mapped_column(Integer, default=0)
    tax_xof: Mapped[int] = mapped_column(Integer, default=0)
    total_xof: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    items: Mapped[list["QuoteItem"]] = relationship(cascade="all, delete-orphan", order_by="QuoteItem.id")


class QuoteItem(Base):
    __tablename__ = "quote_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_quote_item_quantity_positive"), CheckConstraint("unit_price_xof >= 0 AND discount_xof >= 0", name="ck_quote_item_amounts_nonnegative"), CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="ck_quote_item_tax_rate"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"), index=True)
    designation: Mapped[str] = mapped_column(String(240))
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), default=1)
    unit_price_xof: Mapped[int] = mapped_column(Integer)
    discount_xof: Mapped[int] = mapped_column(Integer, default=0)
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("user_id", "number", name="uq_invoice_user_number"), CheckConstraint("status IN ('draft','issued','partially_paid','paid','overdue','cancelled')", name="ck_invoice_status"), CheckConstraint("total_xof >= 0", name="ck_invoice_total_nonnegative"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="RESTRICT"), index=True)
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("activities.id", ondelete="SET NULL"), nullable=True)
    quote_id: Mapped[str | None] = mapped_column(ForeignKey("quotes.id", ondelete="SET NULL"), nullable=True, unique=True)
    number: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="issued")
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    subtotal_xof: Mapped[int] = mapped_column(Integer, default=0)
    tax_xof: Mapped[int] = mapped_column(Integer, default=0)
    total_xof: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    items: Mapped[list["InvoiceItem"]] = relationship(cascade="all, delete-orphan", order_by="InvoiceItem.id")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_invoice_item_quantity_positive"), CheckConstraint("unit_price_xof >= 0 AND discount_xof >= 0", name="ck_invoice_item_amounts_nonnegative"), CheckConstraint("tax_rate >= 0 AND tax_rate <= 100", name="ck_invoice_item_tax_rate"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    designation: Mapped[str] = mapped_column(String(240))
    quantity: Mapped[float] = mapped_column(Numeric(12, 2), default=1)
    unit_price_xof: Mapped[int] = mapped_column(Integer)
    discount_xof: Mapped[int] = mapped_column(Integer, default=0)
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount_xof > 0", name="ck_payment_amount_positive"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), unique=True, nullable=True)
    amount_xof: Mapped[int] = mapped_column(Integer)
    paid_at: Mapped[date] = mapped_column(Date)
    payment_method: Mapped[str] = mapped_column(String(32))


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "category_id", "period_start", "period_end", name="uq_budget_period"), CheckConstraint("period_end >= period_start", name="ck_budget_dates"), CheckConstraint("amount_xof > 0", name="ck_budget_amount_positive"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("activities.id", ondelete="SET NULL"), nullable=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    amount_xof: Mapped[int] = mapped_column(Integer)


class AlertRule(Base):
    __tablename__ = "alert_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rule_type: Mapped[str] = mapped_column(String(40))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[str | None] = mapped_column(ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True)
    severity: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(12), default="active")
    title: Mapped[str] = mapped_column(String(160))
    explanation: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    dedupe_key: Mapped[str] = mapped_column(String(180), index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_setting_user_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class RecurringRule(Base):
    __tablename__ = "recurring_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("activities.id", ondelete="SET NULL"), nullable=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(12))
    description: Mapped[str] = mapped_column(String(240))
    amount_xof: Mapped[int] = mapped_column(Integer)
    frequency: Mapped[str] = mapped_column(String(16))
    next_run: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(100))
    # Les octets restent dans Postgres/SQLite pour survivre aux redéploiements gratuits.
    content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class WorkSession(Base):
    __tablename__ = "work_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("activities.id", ondelete="SET NULL"), nullable=True)
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    service_type: Mapped[str] = mapped_column(String(120), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hours: Mapped[float] = mapped_column(Numeric(8, 2))
    revenue_xof: Mapped[int] = mapped_column(Integer, default=0)
