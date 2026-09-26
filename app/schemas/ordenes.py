from pydantic import BaseModel

from app.schemas.comunes import Dinero


class TituloOrden(BaseModel):
    rubro: int
    id_titulo: int
    numero_titulo: int
    valor: Dinero


class OrdenResponse(BaseModel):
    id_orden: str
    titulos: list[TituloOrden]
