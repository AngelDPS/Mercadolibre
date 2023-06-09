from pydantic import BaseModel as PydanticBaseModel, Field
from decimal import Decimal


class BaseModel(PydanticBaseModel):
    class Config:
        allow_population_by_field_name = True
        anystr_strip_whitespace = True


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
    meli_habilitado: bool = False
    meli_descripcion: str | None
    habilitado: bool | None | str = Field(None, alias='status')
    imagen_url: list[str] | None = None
    # cobra_impuesto: bool = Field(False, alias='taxable')
