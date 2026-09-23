"""create contribuyente and vehiculo tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tipo_identificacion_enum = postgresql.ENUM("CEDULA", "RUC", "PASAPORTE", name="tipo_identificacion_enum", create_type=False)
    tipo_identificacion_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "contribuyente",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tipo_identificacion", tipo_identificacion_enum, nullable=False),
        sa.Column("numero_identificacion", sa.String(length=20), nullable=False),
        sa.UniqueConstraint("numero_identificacion", name="uq_contribuyente_numero_identificacion"),
    )

    op.create_table(
        "vehiculo",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("placa", sa.String(length=20), nullable=False),
        sa.Column("chasis", sa.String(length=50), nullable=True),
        sa.Column("motor", sa.String(length=50), nullable=True),
        sa.Column("anio", sa.Integer(), nullable=True),
        sa.Column("cilindraje", sa.Numeric(10, 2), nullable=True),
        sa.Column("tonelaje", sa.Numeric(10, 2), nullable=True),
        sa.Column("fabricante_id", sa.Integer(), sa.ForeignKey("fabricante.id"), nullable=False),
        sa.Column("tipo_vehiculo_id", sa.Integer(), sa.ForeignKey("tipo_vehiculo.id"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("vehiculo")
    op.drop_table("contribuyente")
    postgresql.ENUM(name="tipo_identificacion_enum").drop(op.get_bind())
