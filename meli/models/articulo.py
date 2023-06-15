from pydantic import BaseModel, Field
from typing import Literal


class SaleTerms(BaseModel):
    id: str
    value_name: str


class Pictures(BaseModel):
    source: str | None = None
    id: str | None = None


class Attributes(BaseModel):
    id: str
    value_name: bool | int | str | None = None
    value_id: str | None = None


class ShippingCost(BaseModel):
    description: str
    cost: str


class Shipping(BaseModel):
    mode: Literal["custom"] = "custom"
    local_pick_up: bool = False
    free_shipping: bool = True
    methods: list = []
    costs: list[ShippingCost] = []


class MArticulo_input(BaseModel):
    title: str = Field('', alias="art_des")
    condition: Literal["new", "used"] = "new"
    category_id: str | None = Field("MLV3530", alias="categoria")
    price: float = Field(0, alias="precio")
    currency_id: Literal["USD", "VES"] = "USD"
    listing_type_id: Literal["gold_pro", "gold_premium",
                             "gold_special", "gold", "silver", "bronze",
                             "free"] | None = Field("free",
                                                    alias="tipo_publicacion")
    available_quantity: int | None = 0
    buying_mode: Literal["buy_it_now"] = "buy_it_now"
    sale_terms: list[SaleTerms] | None = None
    pictures: list[Pictures] | None = None
    attributes: list[Attributes] | None = None
    shipping: Shipping | None = Shipping()
    status: str | None = Field(None, alias='habilitado')
