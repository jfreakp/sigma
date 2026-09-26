from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OrdenTitulo(Base):
    """Relación entre la orden del Sistema de Matriculación y el título emitido en GIM."""

    __tablename__ = "orden_titulo"
    # Una orden puede generar varios títulos: uno por rubro.
    __table_args__ = (UniqueConstraint("id_orden", "entry_id", name="uq_orden_titulo_orden_rubro"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_orden: Mapped[str] = mapped_column(String(100), nullable=False)
    # gimprod.municipalbond.id / .number (sin FK: están en otro esquema, de GIM)
    id_titulo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    numero_titulo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    entry_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("matriculacion.client.id"), nullable=False)
    request: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
