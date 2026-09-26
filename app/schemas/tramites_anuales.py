"""Trámites que generan un título por año: rodaje (3) y recargo por retraso (685)."""
import enum
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.schemas.comunes import Dinero
from app.schemas.tramites_vehiculares import VehiculoTramiteIn

MAX_ANIOS = 30


class TramiteAnual(str, enum.Enum):
    RODAJE = "RODAJE"
    RECARGO_RETRASO = "RECARGO_RETRASO"


class RodajeRequest(BaseModel):
    id_orden: str = Field(min_length=1, max_length=100)
    numero_identificacion: str = Field(min_length=1, max_length=15)
    vehiculo: VehiculoTramiteIn
    avaluo: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    anios: list[int] = Field(min_length=1, max_length=MAX_ANIOS)
    referencia: str | None = Field(default=None, max_length=1200)

    @field_validator("anios")
    @classmethod
    def anios_distintos(cls, anios: list[int]) -> list[int]:
        if len(set(anios)) != len(anios):
            raise ValueError("los años no se pueden repetir")
        if any(anio < 2000 for anio in anios):
            raise ValueError("los años deben ser desde 2000")
        return sorted(anios)


class RecargoRetrasoRequest(BaseModel):
    id_orden: str = Field(min_length=1, max_length=100)
    numero_identificacion: str = Field(min_length=1, max_length=15)
    vehiculo: VehiculoTramiteIn
    fechas_servicio: list[date] = Field(min_length=1, max_length=MAX_ANIOS)
    explicacion: str | None = Field(default=None, max_length=500)

    @field_validator("fechas_servicio")
    @classmethod
    def una_fecha_por_anio(cls, fechas: list[date]) -> list[date]:
        # GIM emite un recargo por cada año de retraso.
        if len({fecha.year for fecha in fechas}) != len(fechas):
            raise ValueError("solo se admite una fecha por año")
        return sorted(fechas)


class TituloAnual(BaseModel):
    anio: int
    id_titulo: int
    numero_titulo: int
    valor: Dinero


class EmisionAnualResponse(BaseModel):
    id_orden: str
    tramite: TramiteAnual
    titulos: list[TituloAnual]
    total: Dinero
    exitoso: bool = True
