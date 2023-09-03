import json
from dynamodb import obtener_articulo
from conexion import MeliConexion
from exceptions import MeliApiError
from handlers.articuloHandler import TipoPublicacion


def meli_cambiar_tipo_pub(input_data: str):
    try:
        data = json.loads(input_data)
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
        return {
            "statusCode": 200,
            "body": "Se cambió exitosamente en Mercadolibre la publicación de "
            f"{data['co_art']} a la categoría {data['tipo_publicacion']}."
        }
    except KeyError as err:
        return {
            "statusCode": 400,
            "body": (
                "No se encontraron los valores esperados en el json de "
                f"entrada.\n{data}\n{err}"
            )
        }
    except MeliApiError as err:
        return {
            "statusCode": err.status_code,
            "body": err.error_message
        }
    except Exception as err:
        return {
            "statusCode": 400,
            "body": f"Ocrrió un error inesperado.\n{err}"
        }
