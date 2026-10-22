import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .db_url import normalize_database_url


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./finpilot.db"))
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# Le ping préalable renouvelle proprement les connexions après la veille de Neon.
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True, pool_pre_ping=True)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
