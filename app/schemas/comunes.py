from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Valores monetarios: Decimal internamente, número en el JSON de respuesta.
Dinero = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


def normalizar_placa(value: str) -> str:
    # Igual que AdjunctHome.findByCode en GIM1.
    return value.strip().upper()
