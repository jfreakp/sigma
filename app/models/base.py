from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    # Tablas propias de la API. Viven en su propio esquema dentro de la base de
    # GIM, separadas de gimprod.
    metadata = MetaData(schema="matriculacion")
