import enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TipoIdentificacion(str, enum.Enum):
    CEDULA = "CEDULA"
    RUC = "RUC"
    PASAPORTE = "PASAPORTE"


class Contribuyente(Base):
    __tablename__ = "contribuyente"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tipo_identificacion: Mapped[TipoIdentificacion] = mapped_column(
        SAEnum(TipoIdentificacion, name="tipo_identificacion_enum"), nullable=False
    )
    numero_identificacion: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
