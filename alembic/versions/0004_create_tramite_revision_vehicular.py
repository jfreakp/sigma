"""create tramite_revision_vehicular table

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the estado_tramite_enum type
    op.execute("CREATE TYPE estado_tramite_enum AS ENUM ('REGISTRADO')")

    tipo_general_enum = postgresql.ENUM(name="tipo_general_enum", create_type=False)
    numero_revision_enum = postgresql.ENUM(name="numero_revision_enum", create_type=False)
    estado_tramite_enum = postgresql.ENUM(name="estado_tramite_enum", create_type=False)

    op.create_table(
        "tramite_revision_vehicular",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contribuyente_id", sa.Integer(), sa.ForeignKey("contribuyente.id"), nullable=False),
        sa.Column("vehiculo_id", sa.Integer(), sa.ForeignKey("vehiculo.id"), nullable=False),
        sa.Column("tipo_general", tipo_general_enum, nullable=False),
        sa.Column("numero_revision", numero_revision_enum, nullable=False),
        sa.Column("fecha_servicio", sa.Date(), nullable=False),
        sa.Column("valor_calculado", sa.Numeric(10, 2), nullable=False),
        sa.Column("explicacion", sa.String(length=500), nullable=True),
        sa.Column("estado", estado_tramite_enum, nullable=False, server_default="REGISTRADO"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("tramite_revision_vehicular")
    postgresql.ENUM(name="estado_tramite_enum").drop(op.get_bind())
