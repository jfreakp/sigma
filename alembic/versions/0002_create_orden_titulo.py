"""create orden_titulo table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SCHEMA = "matriculacion"


def upgrade() -> None:
    op.create_table(
        "orden_titulo",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("id_orden", sa.String(length=100), nullable=False),
        sa.Column("id_titulo", sa.BigInteger(), nullable=False),
        sa.Column("numero_titulo", sa.BigInteger(), nullable=False),
        sa.Column("entry_id", sa.BigInteger(), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA}.client.id"), nullable=False),
        sa.Column("request", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("id_orden", name="uq_orden_titulo_id_orden"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("orden_titulo", schema=SCHEMA)
