from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Activity, Category, Client, Invoice, Payment, Quote, Setting, Transaction, User
from app.seed import initialize_workspace


def test_new_workspace_has_categories_but_no_fictional_business_data():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user = User(email="jeremie@example.test", password_hash="test-only")
        db.add(user)
        db.commit()

        initialize_workspace(db, user.id)
        db.commit()

        assert {row.name for row in db.query(Activity).filter_by(user_id=user.id)} == {
            "Formation en intelligence artificielle", "Coaching", "Montage vidéo",
            "Infographie", "Vente d’ordinateur", "Autres business",
        }
        assert db.query(Category).filter_by(user_id=user.id, kind="expense").count() == 13
        assert db.query(Category).filter_by(user_id=user.id, kind="income").count() == 4
        assert db.query(Client).filter_by(user_id=user.id).count() == 0
        assert db.query(Transaction).filter_by(user_id=user.id).count() == 0
        assert db.query(Quote).filter_by(user_id=user.id).count() == 0
        assert db.query(Invoice).filter_by(user_id=user.id).count() == 0
        assert db.query(Payment).filter_by(user_id=user.id).count() == 0
        preferences = db.query(Setting).filter_by(user_id=user.id, key="preferences").one().value
        assert preferences["monthly_target_xof"] == preferences["annual_target_xof"] == 0

    engine.dispose()
