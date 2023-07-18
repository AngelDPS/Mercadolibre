from pydantic import BaseModel as PydanticBaseModel
from decimal import Decimal
from typing import Literal


class BaseModel(PydanticBaseModel):
    class Config:
        allow_population_by_field_name = True
        anystr_strip_whitespace = True


class MArticulo(BaseModel):
    PK: str | None = None
    SK: str | None = None
    art_des: str | None = ""
    codigoCompania: str | None = None
    codigoTienda: str | None = None
    co_art: str | None = None
    precio: Decimal | None = None
    stock_act: int | None = None
    stock_com: int | None = None
    codigo_barra: str | None = "012345678905"
    referencia: str | None = None
    marca: str | None = "N/A"
    habilitado: bool | None | str = False
    imagen_url: list[str] | None = []
    modelo: str | None = "N/A"
    # cobra_impuesto: bool = Field(False, alias='taxable')


class MArticuloMeli(MArticulo):
    meli_descripcion: str | None = ""
    meli_categoria: str | None = "MLV3530"
    meli_tipo_publicacion: Literal["free", "bronze", "gold_special"] = "free"
    meli_id: dict[str, str | dict[str, str]] | None = {}
