from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import _recompute_alerts
from app.models import Alert, AlertRule, User


def test_recomputing_acknowledged_alerts_does_not_duplicate_them():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user = User(email="alerts@example.test", password_hash="unused")
        db.add(user)
        db.flush()
        db.add(AlertRule(user_id=user.id, rule_type="client_concentration",
                         parameters={"threshold_pct": 40}, is_active=True))
        db.commit()

        args = (db, user.id, {"client_concentration_pct": 65}, [], [], [], {})
        _recompute_alerts(*args)
        alert = db.query(Alert).filter_by(user_id=user.id).one()
        alert.status = "acknowledged"
        db.commit()

        _recompute_alerts(*args)
        assert db.query(Alert).filter_by(user_id=user.id).count() == 1
        assert db.query(Alert).filter_by(user_id=user.id).one().status == "acknowledged"
    engine.dispose()
