from pydantic import BaseModel as PydanticBaseModel
from decimal import Decimal
from typing import Literal


class BaseModel(PydanticBaseModel):
    class Config:
        allow_population_by_field_name = True
        anystr_strip_whitespace = True


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
    # cobra_impuesto: bool = Field(False, alias='taxable')


class Marticulo_meli(Marticulo):
    habilitado: bool = False
    descripcion: str | None = ""
    categoria: str | None = "MLV3530"
    tipo: Literal["free", "bronze", "gold_special"] = "free"
    ID: dict[str, str | dict[str, str]] | None = {}
