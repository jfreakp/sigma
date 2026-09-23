from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.catalogos import NumeroRevision, TipoGeneral
from app.models.contribuyente import TipoIdentificacion
from app.models.tramite_revision_vehicular import EstadoTramite


class VehiculoIn(BaseModel):
    placa: str
    chasis: str | None = None
    motor: str | None = None
    anio: int | None = None
    cilindraje: Decimal | None = None
    tonelaje: Decimal | None = None
    fabricante_id: int
    tipo_vehiculo_id: int


class VehiculoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    placa: str
    chasis: str | None
    motor: str | None
    anio: int | None
    cilindraje: Decimal | None
    tonelaje: Decimal | None
    fabricante_id: int
    tipo_vehiculo_id: int


class TramiteRevisionVehicularCreate(BaseModel):
    tipo_identificacion: TipoIdentificacion
    numero_identificacion: str
    vehiculo: VehiculoIn
    tipo_general: TipoGeneral
    numero_revision: NumeroRevision
    fecha_servicio: date
    explicacion: str | None = None


class TramiteRevisionVehicularOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    vehiculo: VehiculoOut
    tipo_general: TipoGeneral
    numero_revision: NumeroRevision
    fecha_servicio: date
    valor_calculado: Decimal
    explicacion: str | None
    estado: EstadoTramite
    created_at: datetime
