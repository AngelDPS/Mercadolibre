import json
from libs.dynamodb import obtener_articulo
from libs.conexion import MeliConexion
from libs.exceptions import MeliApiError
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
        session.post(f'items/{meli_id}/listing_type',
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
        "co_art": "ARRAN01",
        "tipo_publicacion": "clasico"
    }
    """

    meli_cambiar_tipo_pub(input_data)
