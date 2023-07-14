from typing import Any
from aws_lambda_powertools import Logger
from handlers.eventHandler import procesar_todo
from handlers.articuloHandler import ArticuloHandler

logger = Logger()


@logger.inject_lambda_context(log_event=True)
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
    handler_mapping = {'articulos': ArticuloHandler}
    respuestas = procesar_todo('meli', evento, handler_mapping)
    return respuestas
