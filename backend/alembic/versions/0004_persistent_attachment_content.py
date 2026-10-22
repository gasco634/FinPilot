"""Persist uploaded attachment bytes in the database.

Revision ID: 0004_persistent_attachment_content
Revises: 0003_client_income_details
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_persistent_attachment_content"
down_revision = "0003_client_income_details"
branch_labels = None
depends_on = None


def upgrade():
    # Compatible avec les bases neuves, où create_all peut déjà avoir créé la colonne.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("attachments")}
    if "content" not in columns:
        op.add_column("attachments", sa.Column("content", sa.LargeBinary(), nullable=True))


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("attachments")}
    if "content" in columns:
        op.drop_column("attachments", "content")
