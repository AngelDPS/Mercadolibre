import json
from dynamodb import obtener_articulo, borrar_articulo_meli_id
from conexion import MeliConexion
from exceptions import MeliApiError


def meli_eliminar_publicacion(input_data: str):
    try:
        data = json.loads(input_data)
        meli_id = obtener_articulo(
            data["codigoCompania"], data["codigoTienda"],
            data["co_art"]
        )["meli_id"]["articulo"]
        session = MeliConexion(data["codigoCompania"], data["codigoTienda"])
        session.put(f'items/{meli_id}', json={'status': 'closed'})
        session.put(f'items/{meli_id}', json={'deleted': 'true'})
        borrar_articulo_meli_id(data["codigoCompania"], data["codigoTienda"],
                                data["co_art"])
        return {
            "statusCode": 200,
            "body": f"Artículo {data['co_art']} eliminado exitosamente de "
            "MercadoLibre."
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
    except Exception:
        return {
            "statusCode": 400,
            "body": "Error inesperado."
        }
