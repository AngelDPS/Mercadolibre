from pydantic import BaseModel as PydanticBaseModel
from decimal import Decimal


class BaseModel(PydanticBaseModel):
    class Config:
        allow_population_by_field_name = True
        anystr_strip_whitespace = True


class Meli(BaseModel):
    habilitado: bool = False
    descripcion: str = ""
    categoria: str = "MLV3530"
    ID: dict[str, str | dict[str, str]] = {}


class Marticulo(BaseModel):
    PK: str | None = None
    SK: str | None = None
    art_des: str | None = None
    codigoCompania: str | None = None
    codigoTienda: str | None = None
    co_art: str | None = None
    precio: Decimal | None = None
    stock_act: int | None = None
    stock_com: int | None = None
    codigo_barra: str | None
    referencia: str | None = None
    marca: str | None
    habilitado: bool | None | str = None
    imagen_url: list[str] | None = None
    meli: Meli = Meli()
    # cobra_impuesto: bool = Field(False, alias='taxable')
