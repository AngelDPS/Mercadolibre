import json
from libs.dynamodb import obtener_articulo, borrar_articulo_meli_id
from libs.conexion import MeliConexion
from libs.exceptions import MeliApiError


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


if __name__ == "__main__":
    from os import environ

    environ["LOG_LEVEL"] = "DEBUG"
    environ["POWERTOOLS_SERVICE_NAME"] = "meli"
    environ["NOMBRE_COMPANIA"] = "angel"
    environ["AWS_REGION"] = "us-east-2"
    environ["SQSERROR_URL"] = (
        "https://sqs.us-east-2.amazonaws.com/099375320271/AngelQueue.fifo"
    )
    environ["AWS_PROFILE_NAME"] = "angel"

    input_data = """
    {
        "codigoCompania": "GENERICO2022",
        "codigoTienda": "DLTVA",
        "co_art": "ARRAN01"
    }
    """

    meli_eliminar_publicacion(input_data)
