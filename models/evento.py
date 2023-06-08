from pydantic import BaseModel as PydanticBaseModel, Field
from decimal import Decimal
from enum import Enum


class BaseModel(PydanticBaseModel):
    class Config:
        allow_population_by_field_name = True
        anystr_strip_whitespace = True


class Habilitado(Enum):
    ARCHIVED = 0
    ACTIVE = 1


class Marticulo(BaseModel):
    PK: str | None = None
    SK: str | None = None
    art_des: str | None = Field(None, alias="title")
    codigoCompania: str | None = None
    codigoTienda: str | None = None
    co_art: str | None = None
    precio: Decimal | None = Field(None, alias='price')
    stock_act: int | None = None
    stock_com: int | None = None
    codigo_barra: str | None
    referencia: str | None = None
    marca: str | None
    meli_habilitado: bool | None = None
    meli_descripcion: str | None = None
    habilitado: Habilitado | None | str = Field(None, alias='status')
    # imagen_url: list[str] | None = None
    # cobra_impuesto: bool = Field(False, alias='taxable')
