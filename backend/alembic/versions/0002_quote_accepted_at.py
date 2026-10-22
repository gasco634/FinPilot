"""Record when a quote is accepted.

Revision ID: 0002_quote_accepted_at
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_quote_accepted_at"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    # The initial migration builds tables from current ORM metadata. On a fresh
    # install, accepted_at may therefore already exist before this revision runs.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("quotes")}
    if "accepted_at" not in columns:
        op.add_column("quotes", sa.Column("accepted_at", sa.Date(), nullable=True))


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("quotes")}
    if "accepted_at" in columns:
        op.drop_column("quotes", "accepted_at")
