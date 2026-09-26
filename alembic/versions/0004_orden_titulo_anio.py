"""orden_titulo: columna anio y un título por (orden, rubro, año)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-26

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

SCHEMA = "matriculacion"


def upgrade() -> None:
    op.add_column("orden_titulo", sa.Column("anio", sa.Integer(), nullable=True), schema=SCHEMA)
    op.drop_constraint("uq_orden_titulo_orden_rubro", "orden_titulo", schema=SCHEMA, type_="unique")
    # NULLS NOT DISTINCT (Postgres >= 15): los rubros sin año siguen admitiendo un solo título por orden.
    op.execute(
        f"ALTER TABLE {SCHEMA}.orden_titulo ADD CONSTRAINT uq_orden_titulo_orden_rubro_anio "
        "UNIQUE NULLS NOT DISTINCT (id_orden, entry_id, anio)"
    )


def downgrade() -> None:
    # Falla si alguna orden ya tiene varios años del mismo rubro.
    op.drop_constraint("uq_orden_titulo_orden_rubro_anio", "orden_titulo", schema=SCHEMA, type_="unique")
    op.create_unique_constraint(
        "uq_orden_titulo_orden_rubro", "orden_titulo", ["id_orden", "entry_id"], schema=SCHEMA
    )
    op.drop_column("orden_titulo", "anio", schema=SCHEMA)
