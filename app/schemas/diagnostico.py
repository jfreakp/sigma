import enum

from pydantic import BaseModel


class EstadoReglas(str, enum.Enum):
    AL_DIA = "AL_DIA"
    DESACTUALIZADO = "DESACTUALIZADO"


class ReglaRodaje(BaseModel):
    rubro: int
    descripcion: str
    sin_cambios: bool


class DiagnosticoReglasResponse(BaseModel):
    estado: EstadoReglas
    mensaje: str
    reglas: list[ReglaRodaje]
