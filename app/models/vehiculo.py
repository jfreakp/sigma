from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Vehiculo(Base):
    __tablename__ = "vehiculo"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    placa: Mapped[str] = mapped_column(String(20), nullable=False)
    chasis: Mapped[str | None] = mapped_column(String(50), nullable=True)
    motor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    anio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cilindraje: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    tonelaje: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fabricante_id: Mapped[int] = mapped_column(ForeignKey("fabricante.id"), nullable=False)
    tipo_vehiculo_id: Mapped[int] = mapped_column(ForeignKey("tipo_vehiculo.id"), nullable=False)
