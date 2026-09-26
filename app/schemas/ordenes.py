from pydantic import BaseModel

from app.schemas.comunes import Dinero


class TituloOrden(BaseModel):
    rubro: int
    anio: int | None  # solo en rubros anuales (rodaje, recargo)
    id_titulo: int
    numero_titulo: int
    valor: Dinero


class OrdenResponse(BaseModel):
    id_orden: str
    titulos: list[TituloOrden]
