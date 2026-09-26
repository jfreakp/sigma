import enum
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.comunes import Dinero, normalizar_placa


class Tramite(str, enum.Enum):
    DUPLICADO_MATRICULA = "DUPLICADO_MATRICULA"
    INSCRIPCION_GRAVAMEN = "INSCRIPCION_GRAVAMEN"
    LEVANTAMIENTO_GRAVAMEN = "LEVANTAMIENTO_GRAVAMEN"
    MODIFICACION_CARACTERISTICAS = "MODIFICACION_CARACTERISTICAS"
    BLOQUEO_DESBLOQUEO = "BLOQUEO_DESBLOQUEO"
    CERTIFICADO_UNICO_VEHICULAR = "CERTIFICADO_UNICO_VEHICULAR"
    CERTIFICADO_POSEER_VEHICULO = "CERTIFICADO_POSEER_VEHICULO"


class VehiculoTramiteIn(BaseModel):
    """Solo la placa es obligatoria: el resto se copia del último vehículo con esa
    placa en GIM; si se envía, reemplaza al valor copiado."""

    placa: str = Field(min_length=1, max_length=30)
    chasis: str | None = Field(default=None, max_length=255)
    motor: str | None = Field(default=None, max_length=255)
    anio: int | None = Field(default=None, ge=1900, le=2100)
    cilindraje: Decimal | None = Field(default=None, ge=0)
    tonelaje: Decimal | None = Field(default=None, ge=0)
    fabricante_id: int | None = None
    tipo_vehiculo_id: int | None = None

    @field_validator("placa")
    @classmethod
    def placa_en_mayusculas(cls, value: str) -> str:
        return normalizar_placa(value)


class TramiteVehicularRequest(BaseModel):
    id_orden: str = Field(min_length=1, max_length=100)
    tramite: Tramite
    numero_identificacion: str = Field(min_length=1, max_length=15)
    vehiculo: VehiculoTramiteIn | None = None
    explicacion: str | None = Field(default=None, max_length=500)
    referencia: str | None = Field(default=None, max_length=1200)


class TramiteVehicularResponse(BaseModel):
    id_orden: str
    tramite: Tramite
    id_titulo: int
    numero_titulo: int
    valor: Dinero
    exitoso: bool = True
