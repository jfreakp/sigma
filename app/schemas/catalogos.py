from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.catalogos import NumeroRevision, TipoGeneral


class FabricanteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


class TipoVehiculoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


class TarifaRevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo_general: TipoGeneral
    numero_revision: NumeroRevision
    porcentaje: Decimal
