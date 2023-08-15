from boto3.dynamodb.types import TypeDeserializer
from libs.util import ItemHandler
from handlers.sqsHandler import obtener_records_en_cola
from json import dumps
from aws_lambda_powertools import Logger

logger = Logger(service="event_handler")


def deserializar(dynamo_db_dict: dict) -> dict:
    """Deserializa un diccionario serializado segun DynamoDB

    Args:
        Image (dict): Diccionario serializado segun DynamoDB

    Returns:
        dict: Diccionario deserealizado
    """
    deserializer = TypeDeserializer()
    try:
        return {k: deserializer.deserialize(v)
                for k, v in dynamo_db_dict.items()}
    except TypeError:
        logger.exception('Los valores de "NewImage" y "OldImage" deberían '
                         'ser diccionarios no-vacíos cuya key corresponde '
                         'a un tipo de dato de DynamoDB soportado por '
                         'boto3.')
        raise


def obtener_cambios(new_dict: dict, old_dict: dict) -> dict:
    """Obtiene los cambios realizados entre dos diccionarios, con
    versiones posterior y previa.
    Los cambios se obtienen de forma recursiva. Es decir, se obtienen los
    cambios entre los diccionarios principales y los diccionarios anidados
    en los mismos.

    Args:
        new_dict (dict): Diccionario con data nueva.
        old_dict (dict): Diccionario con data previa.

    Returns:
        dict: Diccionario con las entradas que fueron modificadas entre las
        versiones, con los valores del diccionario posterior.
    """
    cambios = {}
    for k, v in old_dict.items():
        # if isinstance(v, dict):
        # cambios[k] = EventHandler.obtener_cambios(new_dict.get(k,{}),
        #                                           v)
        if v != new_dict.get(k) and k != "updated_at":
            cambios[k] = new_dict.get(k)
    cambios |= {k: v for k, v in new_dict.items() if k not in old_dict}
    # cambios = {k: v for k, v in cambios.items()
    #            if (v or (v is None or v == 0))}
    return cambios


def formatear_record(record: dict) -> tuple[dict | None]:
    """Recibe el record y lo formatea, regresando la imagen anterior
    y los cambios realizados de la data enviada por la base de datos
    para su posterior manipulación.

    Args:
        record (dict): Record de un evento de DynamoDB.

    Returns:
        tuple[dict]: Tupla con los diccionarios deserealizados de los
        cambios registrados por el record y la imagen previa a los cambios.
    """
    try:
        new_image = EventHandler.deserializar(
            record['dynamodb']['NewImage']
        )
        old_image = EventHandler.deserializar(
            record['dynamodb'].get('OldImage', {})
        )
        cambios = EventHandler.obtener_cambios(new_image, old_image)
        logger.debug(f'{cambios = }')
        return old_image, cambios
    except KeyError:
        logger.exception("Formato inesperado para el record.\n"
                         "El record debería tener los objetos\n"
                         '{\n\t...,\n\t"dynamobd": {\n\t\t...\n\t\t'
                         '"NewImage": ...\n\t}\n}')
        raise


class EventHandler:
    deserializar = staticmethod(deserializar)
    obtener_cambios = staticmethod(obtener_cambios)
    formatear_record = staticmethod(formatear_record)

    def __init__(self, record: dict, handler_mapping: dict[str, ItemHandler]):
        """Constructor de la instancia encargada de procesar el record

        Args:
            record (dict): Record de un evento de DynamoDB.
        """
        self.old_image, self.cambios = (
            EventHandler.formatear_record(record)
        )
        self.handler_mapping = handler_mapping

    @property
    def handler(self) -> ItemHandler:
        """Obtiene un handler para el record según el entity del ítem que
        provocó el evento.

        Returns:
            ItemHandler: El manipulador adecuado para el record.
        """
        try:
            handler = self.handler_mapping[self.old_image.get('entity')
                                           or self.cambios.get('entity')]
            logger.info(f"El evento será procesado por {handler}.")
            return handler
        except KeyError as err:
            raise NotImplementedError(
                "El evento corresponde a una entidad de "
                f"{self.old_image.get('entity') or self.cambios.get('entity')}"
                ", cuyo proceso no está implementado."
            ) from err

    def ejecutar(self) -> dict[str, str]:
        """Método encargado de ejecutar la acción solicitada por el evento ya
        procesado.

        Returns:
            dict[str, str]: Diccionario con la información del estado de la
            acción y el resultado obtenido.
        """
        return self.handler(self).ejecutar()


def procesar_todo(evento: list[dict],
                  handler_mapping: dict[str, ItemHandler]):
    try:
        record = evento["Records"][0]
    except KeyError:
        record = evento[0]
    records_en_cola, sqs_queue = obtener_records_en_cola(record)
    r = []

    logger.info("Records para procesar: "
                f"{[rec.contenido for rec in records_en_cola]}")

    for n, record in enumerate(records_en_cola):
        try:
            r.append(EventHandler(record.contenido,
                                  handler_mapping).ejecutar())
            logger.debug(r[-1])
        except NotImplementedError:
            logger.warning("La acción requerida no está implementada y se "
                           "ignorará el evento.")
            continue
        except Exception as err:
            msg = (f"Ocurrió un error manejado el evento:\n{record.contenido}."
                   f"Se levantó la excepción '{err}'.")
            logger.exception(msg)
            if n == 0:
                raise Exception(msg) from err
            continue

        if isinstance(r[-1], dict) and r[-1].get("statusCode") >= 400:
            if n == 0 and r[-1].get("statusCode") != 400:
                sqs_queue.send_message(
                    MessageBody=dumps(evento),
                    MessageGroupId="ERROR_QUEUE",
                    MessageDeduplicationId=record.contenido.get("eventID")
                )
            continue
        else:
            record.borrar_de_cola()

    return r
