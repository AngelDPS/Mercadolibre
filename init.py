from typing import Any
from aws_lambda_powertools import Logger
from libs.util import get_parameter
from handlers.sqsHandler import obtener_eventos_en_cola
from handlers.eventHandler import EventHandler
from handlers.articuloHandler import ArticuloHandler

logger = Logger(service="meli",
                level=get_parameter("loglevel") or "WARNING")


@logger.inject_lambda_context(log_event=True)
def lambda_handler(evento_nuevo: list[dict],
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
    eventos_en_cola = obtener_eventos_en_cola(service_name="meli",
                                              evento_nuevo=evento_nuevo)
    handler_mapping = {'articulos': ArticuloHandler}
    r = []

    logger.info("Eventos para procesar: "
                f"{[ev.contenido[0] for ev in eventos_en_cola]}")

    for n, evento in enumerate(eventos_en_cola):
        try:
            for ev in evento.contenido:
                r.append(EventHandler(ev, handler_mapping).ejecutar())
                logger.debug(r[-1])
        except NotImplementedError:
            logger.warning("La acción requerida no está implementada y se "
                           "ignorará el evento.")
            continue
        except Exception as err:
            mensaje = (f"Ocurrió un error manejado el evento:\n{ev}."
                       f"Se levantó la excepción '{err}'.")
            logger.exception(mensaje)
            if n == 0:
                raise Exception(mensaje) from err
            continue
        else:
            evento.borrar_de_cola()

    return r
