from typing import Any
from aws_lambda_powertools import Logger
from handlers.eventHandler import procesar_todo, obtener_cambios
from handlers.articuloHandler import ArticuloHandler
from libs.util import filtro_campos_completos

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
    try:
        filtro_campos_completos(evento)
    except ValueError:
        return {
            "statusCode": 400,
            "body": "No se encontraron campos completos en el registro"
        }

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
        respuestas = procesar_todo(evento, handler_mapping)
        return respuestas
