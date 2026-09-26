"""orden_titulo: un título por (orden, rubro) en lugar de uno por orden

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-26

"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

SCHEMA = "matriculacion"


def upgrade() -> None:
    op.drop_constraint("uq_orden_titulo_id_orden", "orden_titulo", schema=SCHEMA, type_="unique")
    op.create_unique_constraint(
        "uq_orden_titulo_orden_rubro", "orden_titulo", ["id_orden", "entry_id"], schema=SCHEMA
    )


def downgrade() -> None:
    # Falla si alguna orden ya tiene títulos de varios rubros.
    op.drop_constraint("uq_orden_titulo_orden_rubro", "orden_titulo", schema=SCHEMA, type_="unique")
    op.create_unique_constraint("uq_orden_titulo_id_orden", "orden_titulo", ["id_orden"], schema=SCHEMA)
