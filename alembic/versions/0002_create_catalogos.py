"""create catalogos tables (fabricante, tipo_vehiculo, tarifa_revision, parametro_sbu)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TIPO_GENERAL_VALUES = ("BUSES", "BUSETAS", "LIVIANOS", "MOTOS", "PESADOS", "PLATAFORMAS", "TAXIS")
NUMERO_REVISION_VALUES = ("PRIMERA", "SEGUNDA", "TERCERA", "CUARTA", "ORDINARIA")

# tipo_general -> {numero_revision: porcentaje}, confirmado contra gimprod.vehiclerevisionvalues
TARIFAS = {
    "BUSES": {"PRIMERA": "8.00", "SEGUNDA": "0.00", "TERCERA": "4.00", "CUARTA": "8.00", "ORDINARIA": "4.00"},
    "BUSETAS": {"PRIMERA": "8.00", "SEGUNDA": "0.00", "TERCERA": "4.00", "CUARTA": "8.00", "ORDINARIA": "4.00"},
    "LIVIANOS": {"PRIMERA": "5.00", "SEGUNDA": "0.00", "TERCERA": "2.50", "CUARTA": "5.00", "ORDINARIA": "2.50"},
    "MOTOS": {"PRIMERA": "3.00", "SEGUNDA": "0.00", "TERCERA": "1.50", "CUARTA": "3.00", "ORDINARIA": "1.50"},
    "PESADOS": {"PRIMERA": "12.00", "SEGUNDA": "0.00", "TERCERA": "6.00", "CUARTA": "12.00", "ORDINARIA": "6.00"},
    "PLATAFORMAS": {"PRIMERA": "8.00", "SEGUNDA": "0.00", "TERCERA": "4.00", "CUARTA": "8.00", "ORDINARIA": "4.00"},
    "TAXIS": {"PRIMERA": "4.00", "SEGUNDA": "0.00", "TERCERA": "2.00", "CUARTA": "4.00", "ORDINARIA": "2.00"},
}


def upgrade() -> None:
    op.create_table(
        "fabricante",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("nombre", name="uq_fabricante_nombre"),
    )

    op.create_table(
        "tipo_vehiculo",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("nombre", name="uq_tipo_vehiculo_nombre"),
    )

    # Create ENUMs first for tarifa_revision table
    tipo_general_enum = postgresql.ENUM(*TIPO_GENERAL_VALUES, name="tipo_general_enum", create_type=False)
    numero_revision_enum = postgresql.ENUM(*NUMERO_REVISION_VALUES, name="numero_revision_enum", create_type=False)
    tipo_general_enum.create(op.get_bind(), checkfirst=True)
    numero_revision_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tarifa_revision",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tipo_general", tipo_general_enum, nullable=False),
        sa.Column("numero_revision", numero_revision_enum, nullable=False),
        sa.Column("porcentaje", sa.Numeric(5, 2), nullable=False),
    )

    op.create_table(
        "parametro_sbu",
        sa.Column("anio", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("valor", sa.Numeric(10, 2), nullable=False),
    )

    tarifa_revision_table = sa.table(
        "tarifa_revision",
        sa.column("tipo_general", tipo_general_enum),
        sa.column("numero_revision", numero_revision_enum),
        sa.column("porcentaje", sa.Numeric),
    )
    rows = [
        {"tipo_general": tipo, "numero_revision": numero, "porcentaje": porcentaje}
        for tipo, por_numero in TARIFAS.items()
        for numero, porcentaje in por_numero.items()
    ]
    op.bulk_insert(tarifa_revision_table, rows)


def downgrade() -> None:
    op.drop_table("parametro_sbu")
    op.drop_table("tarifa_revision")
    op.drop_table("tipo_vehiculo")
    op.drop_table("fabricante")
    op.execute("DROP TYPE numero_revision_enum CASCADE")
    op.execute("DROP TYPE tipo_general_enum CASCADE")
