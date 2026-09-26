"""tramos del rodaje y huellas de las reglas de GIM como datos

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-26

Copia legible de las reglas Drools del rodaje en GIM (entrydefinition 3, rubro 3, y
1001, sub-rubro 713), tal como están en diario_20260505 el 2026-09-26.
"""
from decimal import Decimal

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

SCHEMA = "matriculacion"

# (desde, hasta, valor, servicios_administrativos, descripcion); hasta None = sin límite.
TRAMOS_RODAJE = [
    ("0", "1000", "0", "2.00", "Pago por servicios administrativos"),
    ("1001", "4000", "5", "0", "Vehículo con valor entre 1001 - 4000"),
    ("4001", "8000", "10", "0", "Vehículo con valor entre 4001 - 8000"),
    ("8001", "12000", "15", "0", "Vehículo con valor entre 8001 - 12000"),
    ("12001", "16000", "20", "0", "Vehículo con valor entre 12001 - 16000"),
    ("16001", "20000", "25", "0", "Vehículo con valor entre 16001 - 20000"),
    ("20001", "30000", "30", "0", "Vehículo con valor entre 20001 - 30000"),
    ("30001", "40000", "50", "0", "Vehículo con valor entre 30001 - 40000"),
    ("40001", None, "70", "0", "Vehículo con valor mayor a 40000"),
]

# (entry_id, huella SHA-256 del texto de la regla, descripcion)
HUELLAS_REGLAS = [
    (3, "b1e60702e86bfbae9c2d97a6eaf76fd6710e095dbcd3ba26ce8ec61c557b82ee", "Impuesto al rodaje de vehiculos (entrydefinition 3)"),
    (713, "0cb76a9153cc0c50e27941dc4d971904a1308a6795e090843e8b6278099de8be", "Exoneración o no sujeto pasivo (entrydefinition 1001)"),
]


def _decimal(valor: str | None) -> Decimal | None:
    return Decimal(valor) if valor is not None else None


def upgrade() -> None:
    tramo = op.create_table(
        "tramo_rodaje",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("desde", sa.Numeric(14, 2), nullable=False),
        sa.Column("hasta", sa.Numeric(14, 2), nullable=True),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("servicios_administrativos", sa.Numeric(12, 2), nullable=False),
        sa.Column("descripcion", sa.String(length=200), nullable=False),
        schema=SCHEMA,
    )
    regla = op.create_table(
        "regla_gim_replicada",
        sa.Column("entry_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("huella_sha256", sa.String(length=64), nullable=False),
        sa.Column("descripcion", sa.String(length=200), nullable=False),
        schema=SCHEMA,
    )
    op.bulk_insert(
        tramo,
        [
            {
                "desde": _decimal(desde),
                "hasta": _decimal(hasta),
                "valor": _decimal(valor),
                "servicios_administrativos": _decimal(servicios),
                "descripcion": descripcion,
            }
            for desde, hasta, valor, servicios, descripcion in TRAMOS_RODAJE
        ],
    )
    op.bulk_insert(
        regla,
        [{"entry_id": entry_id, "huella_sha256": huella, "descripcion": descripcion} for entry_id, huella, descripcion in HUELLAS_REGLAS],
    )


def downgrade() -> None:
    op.drop_table("regla_gim_replicada", schema=SCHEMA)
    op.drop_table("tramo_rodaje", schema=SCHEMA)
