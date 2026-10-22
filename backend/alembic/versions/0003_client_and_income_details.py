"""Add structured client names and income classification.

Revision ID: 0003_client_income_details
Revises: 0002_quote_accepted_at
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_client_income_details"
down_revision = "0002_quote_accepted_at"
branch_labels = None
depends_on = None


def upgrade():
    # La migration initiale suit les modèles courants ; éviter les doublons sur base neuve.
    bind = op.get_bind()
    client_columns = {column["name"] for column in sa.inspect(bind).get_columns("clients")}
    transaction_columns = {column["name"] for column in sa.inspect(bind).get_columns("transactions")}
    if "first_name" not in client_columns:
        op.add_column("clients", sa.Column("first_name", sa.String(length=80), nullable=True))
    if "last_name" not in client_columns:
        op.add_column("clients", sa.Column("last_name", sa.String(length=80), nullable=True))
    if "income_type" not in transaction_columns:
        op.add_column("transactions", sa.Column("income_type", sa.String(length=20), nullable=True))


def downgrade():
    bind = op.get_bind()
    client_columns = {column["name"] for column in sa.inspect(bind).get_columns("clients")}
    transaction_columns = {column["name"] for column in sa.inspect(bind).get_columns("transactions")}
    if "income_type" in transaction_columns:
        op.drop_column("transactions", "income_type")
    if "last_name" in client_columns:
        op.drop_column("clients", "last_name")
    if "first_name" in client_columns:
        op.drop_column("clients", "first_name")
