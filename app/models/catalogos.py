import enum
from decimal import Decimal

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TipoGeneral(str, enum.Enum):
    BUSES = "BUSES"
    BUSETAS = "BUSETAS"
    LIVIANOS = "LIVIANOS"
    MOTOS = "MOTOS"
    PESADOS = "PESADOS"
    PLATAFORMAS = "PLATAFORMAS"
    TAXIS = "TAXIS"


class NumeroRevision(str, enum.Enum):
    PRIMERA = "PRIMERA"
    SEGUNDA = "SEGUNDA"
    TERCERA = "TERCERA"
    CUARTA = "CUARTA"
    ORDINARIA = "ORDINARIA"


class Fabricante(Base):
    __tablename__ = "fabricante"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    nombre: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)


class TipoVehiculo(Base):
    __tablename__ = "tipo_vehiculo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    nombre: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)


class TarifaRevision(Base):
    __tablename__ = "tarifa_revision"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tipo_general: Mapped[TipoGeneral] = mapped_column(SAEnum(TipoGeneral, name="tipo_general_enum"), nullable=False)
    numero_revision: Mapped[NumeroRevision] = mapped_column(
        SAEnum(NumeroRevision, name="numero_revision_enum"), nullable=False
    )
    porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)


class ParametroSBU(Base):
    __tablename__ = "parametro_sbu"

    anio: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
