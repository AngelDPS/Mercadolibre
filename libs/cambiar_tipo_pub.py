import json
from dynamodb import obtener_articulo
from conexion import MeliConexion
from handlers.articuloHandler import TipoPublicacion


def meli_cambiar_tipo_pub(json_input: str):
    data = json.load(json_input)
    tipo_publicacion = TipoPublicacion[
        data["tipo_publicacion"].upper()
    ].value
    meli_id = obtener_articulo(
        data["codigoCompania"], data["codigoTienda"],
        data["co_art"]
    )["meli_id"]["articulo"]
    session = MeliConexion(data["codigoCompania"], data["codigoTienda"])
    session.put(f'items/{meli_id}/listing_type',
                json={'id': tipo_publicacion})
