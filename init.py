from typing import Any
from aws_lambda_powertools import Logger
from handlers.eventHandler import procesar_todo, obtener_cambios
from handlers.articuloHandler import ArticuloHandler
from libs.util import filtro_campos_completos
from os import environ, getenv

logger = Logger()


# @logger.inject_lambda_context(log_event=True)
def lambda_handler(evento: list[dict],
                   context: Any) -> list[dict[str, str]]:
    """Manipulador de los eventos de entrada provenientes de
    una base de datos DynamoDB con el registro de inventario para
    ser manejados en una tienda de MercadoLibre.

    Args:
        event (list[dict]): Lista de eventos provenientes de DynamoDB
        context (Any): context

    Raises:
        Exception: Levanta una excepción en caso de falla general. Trae consigo
        el evento que causó la excepción y la excepción padre que lo generó.

    Returns:
        list[dict[str, str]]: Lista de diccionarios con los mensajes
        retornados por cada evento procesado.
    """
    if getenv("AWS_EXECUTION_ENV") is None:
        environ["NOMBRE_COMPANIA"] = "generico2022"
        environ["AWS_REGION"] = "us-east-2"
        environ["SQSERROR_URL"] = (
            "https://sqs.us-east-2.amazonaws.com/276507440195/TestMeliErrorQueue.fifo"
        )
        environ["AWS_PROFILE_NAME"] = "generic-dev"

    try:
        filtro_campos_completos(evento)
    except ValueError:
        return {
            "statusCode": 400,
            "body": "No se encontraron campos completos en el registro"
        }

    logger.info(f"Evento: {evento}")
    try:
        cambios = obtener_cambios(
            evento["Records"][0]["dynamodb"]["NewImage"],
            evento["Records"][0]["dynamodb"].get("OldImage", {})
        )
    except IndexError:
        cambios = obtener_cambios(evento[0]["dynamodb"]["NewImage"],
                                  evento[0]["dynamodb"].get("OldImage", {}))
    cambios.pop("meli_id", None)
    cambios.pop("meli_error", None)
    logger.info(f"Cambios: {cambios}")
    if not cambios:
        logger.info("No se encontraron cambios en el registro")
        return {
            "statusCode": 201,
            "body": "No se encontraron cambios en el registro"
        }
    else:
        handler_mapping = {'articulos': ArticuloHandler}
        respuestas = procesar_todo('meli', evento, handler_mapping)
        return respuestas


if __name__ == "__main__":
    evento = {"Records": [
        {
    "eventID": "a908e25ca8323aebf09c96f8aa054661",
    "eventName": "INSERT",
    "eventVersion": "1.1",
    "eventSource": "aws:dynamodb",
    "awsRegion": "us-east-2",
    "dynamodb": {
      "ApproximateCreationDateTime": 1689266391,
      "Keys": {
        "SK": { "S": "METADATA" },
        "PK": { "S": "GENERICO2022#DLTVA#ACCE10" }
      },
      "NewImage": {
        "imagen_url": {
          "L": [
            {
              "S": "articulo_ACCE01_599.webp"
            }
          ]
        },
        "meli_habilitado": { "N": "1" },
        "prec_vta1": { "N": "5.0" },
        "prec_vta3": { "N": "1.27" },
        "stock_com": { "N": "5" },
        "tipo": { "S": "TIENDA" },
        "ubicacion": { "S": "P01" },
        "prec_vta2": { "N": "10" },
        "co_lin": { "S": "41" },
        "created_at": { "S": "2023-07-13T16:39:48.230431Z" },
        "unidad_empaque": { "NULL": True },
        "codigoTienda": { "S": "DLTVA" },
        "marca": { "NULL": True },
        "updated_at": { "S": "2023-07-13T16:39:48.230431Z" },
        "iva": { "N": "16" },
        "codigoCompania": { "S": "GENERICO2022" },
        "SK": { "S": "METADATA" },
        "moneda": { "N": "2" },
        "habilitado": { "N": "1" },
        "cantidad_empaque": { "N": "0" },
        "art_des": {
          "S": "ABRAZADERA EMT 3/4\" "
        },
        "co_art": { "S": "ACCE10" },
        "meli_categoria": { "S": "MLV3530" },
        "unidad": { "S": "PAR" },
        "stock_act": { "N": "0" },
        "PK": { "S": "GENERICO2022#DLTVA#ACCE10" },
        "entity": { "S": "articulos" },
        "referencia": { "NULL": True }
      },
      "SequenceNumber": "154076100000000029021853684",
      "SizeBytes": 447,
      "StreamViewType": "NEW_AND_OLD_IMAGES"
    },
    "eventSourceARN": "arn:aws:dynamodb:us-east-2:276507440195:table/generico2022-db/stream/2023-07-12T14:33:20.801"
  }
    ]}
    
    lambda_handler(evento, {})