import json
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import main
from app.database import Base, get_db
from app.models import Attachment, Client, Quote, QuoteItem, Transaction, User
from app.security import create_access_token


def test_backup_restore_keeps_attachment_bytes_and_replaces_records(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    user_id = "user-backup-test"
    source_file = tmp_path / "receipt.pdf"
    source_bytes = b"FinPilot attachment fixture"
    source_file.write_bytes(source_bytes)
    with Session(engine) as db:
        user = User(id=user_id, email="backup@example.test", password_hash="unused")
        db.add(user)
        db.flush()
        client = Client(user_id=user_id, name="Client fixture")
        db.add(client)
        db.flush()
        quote = Quote(user_id=user_id, client_id=client.id, number="DEV-2026-001", status="draft",
                      issue_date=date(2026, 10, 1), valid_until=date(2026, 10, 31),
                      subtotal_xof=15000, tax_xof=0, total_xof=15000)
        db.add(quote)
        db.flush()
        db.add(QuoteItem(quote_id=quote.id, designation="Session", quantity=1.5,
                         unit_price_xof=10000, discount_xof=0, tax_rate=0))
        transaction = Transaction(user_id=user_id, kind="expense", amount_xof=12000,
                                  transaction_date=date(2026, 10, 1), status="received",
                                  description="Test de sauvegarde")
        db.add(transaction)
        db.flush()
        db.add(Attachment(user_id=user_id, transaction_id=transaction.id, filename="receipt.pdf",
                          storage_path=str(source_file), mime_type="application/pdf"))
        db.commit()

    def override_get_db():
        with Session(engine) as db:
            yield db

    monkeypatch.setitem(main.app.dependency_overrides, get_db, override_get_db)
    monkeypatch.setattr(main, "ATTACHMENT_UPLOAD_ROOT", tmp_path / "restored-files")
    headers = {"Authorization": f"Bearer {create_access_token(user_id)}"}
    client = TestClient(main.app)

    backup_response = client.get("/api/settings/backup", headers=headers)
    assert backup_response.status_code == 200
    backup = backup_response.json()
    assert backup["format"] == "finpilot-user-backup-v2"
    assert backup["tables"]["attachments"][0]["content_base64"]
    assert backup["tables"]["quote_items"][0]["quantity"] == 1.5

    source_file.write_bytes(b"old data that must be replaced")
    restore_response = client.post("/api/settings/restore", headers=headers,
                                   files={"file": ("backup.json", json.dumps(backup).encode(), "application/json")})
    assert restore_response.status_code == 200, restore_response.text

    with Session(engine) as db:
        attachment = db.query(Attachment).filter_by(user_id=user_id).one()
        restored_transaction = db.query(Transaction).filter_by(user_id=user_id).one()
        restored_item = db.query(QuoteItem).one()
        assert attachment.transaction_id == restored_transaction.id
        assert float(restored_item.quantity) == 1.5
        attachment_id = attachment.id
        restored_path = attachment.storage_path
    assert open(restored_path, "rb").read() == source_bytes

    download_response = client.get(f"/api/attachments/{attachment_id}", headers=headers)
    assert download_response.status_code == 200
    assert download_response.content == source_bytes
    client.close()
    engine.dispose()
