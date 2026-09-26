from decimal import Decimal

from sqlalchemy import BigInteger, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TramoRodaje(Base):
    """Tramos del impuesto al rodaje (rubro 3): réplica legible de la regla Drools de GIM
    (entrydefinition 3 y, para servicios_administrativos, la del sub-rubro 713).

    Límites inclusivos, igual que la regla. Si Rentas cambia la regla en GIM, se
    actualiza esta tabla con SQL (y la huella en regla_gim_replicada); no hace falta
    tocar código.
    """

    __tablename__ = "tramo_rodaje"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    desde: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    hasta: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)  # NULL: sin límite superior
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    servicios_administrativos: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # sub-rubro 713
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)


class ReglaGimReplicada(Base):
    """Huella (SHA-256) del texto de cada regla Drools de GIM que la API replica.

    Si la regla vigente en GIM ya no tiene esta huella, la API no emite: primero hay que
    revisar la réplica (tramo_rodaje) y registrar aquí la huella nueva.
    """

    __tablename__ = "regla_gim_replicada"

    entry_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    huella_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)
