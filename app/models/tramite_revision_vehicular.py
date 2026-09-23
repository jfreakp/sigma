import enum
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.catalogos import NumeroRevision, TipoGeneral
from app.models.vehiculo import Vehiculo


class EstadoTramite(str, enum.Enum):
    REGISTRADO = "REGISTRADO"


class TramiteRevisionVehicular(Base):
    __tablename__ = "tramite_revision_vehicular"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contribuyente_id: Mapped[int] = mapped_column(ForeignKey("contribuyente.id"), nullable=False)
    vehiculo_id: Mapped[int] = mapped_column(ForeignKey("vehiculo.id"), nullable=False)
    vehiculo: Mapped["Vehiculo"] = relationship(lazy="raise")
    tipo_general: Mapped[TipoGeneral] = mapped_column(SAEnum(TipoGeneral, name="tipo_general_enum"), nullable=False)
    numero_revision: Mapped[NumeroRevision] = mapped_column(
        SAEnum(NumeroRevision, name="numero_revision_enum"), nullable=False
    )
    fecha_servicio: Mapped[date] = mapped_column(Date, nullable=False)
    valor_calculado: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    explicacion: Mapped[str | None] = mapped_column(String(500), nullable=True)
    estado: Mapped[EstadoTramite] = mapped_column(
        SAEnum(EstadoTramite, name="estado_tramite_enum"), nullable=False, default=EstadoTramite.REGISTRADO
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
