import enum
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer, field_validator


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


# Valores monetarios: Decimal internamente, número en el JSON de respuesta.
Dinero = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


class VehiculoIn(BaseModel):
    placa: str = Field(min_length=1, max_length=30)
    chasis: str | None = Field(default=None, max_length=255)
    motor: str | None = Field(default=None, max_length=255)
    anio: int | None = Field(default=None, ge=1900, le=2100)
    cilindraje: Decimal | None = Field(default=None, ge=0)
    tonelaje: Decimal | None = Field(default=None, ge=0)
    fabricante_id: int
    tipo_vehiculo_id: int

    @field_validator("placa")
    @classmethod
    def placa_en_mayusculas(cls, value: str) -> str:
        # Igual que AdjunctHome.findByCode en GIM1.
        return value.strip().upper()


class EmisionRevisionRequest(BaseModel):
    id_orden: str = Field(min_length=1, max_length=100)
    numero_identificacion: str = Field(min_length=1, max_length=15)
    vehiculo: VehiculoIn
    tipo_general: TipoGeneral
    numero_revision: NumeroRevision
    explicacion: str = Field(min_length=1, max_length=500)
    referencia: str | None = Field(default=None, max_length=1200)


class EmisionRevisionResponse(BaseModel):
    id_orden: str
    id_titulo: int
    numero_titulo: int
    valor: Dinero
    exitoso: bool = True
