from boto3.dynamodb.types import TypeDeserializer
from libs.util import ItemHandler, get_parameter
from handlers.sqsHandler import obtener_eventos_en_cola
from aws_lambda_powertools import Logger

logger = Logger(service="event_handler",
                level=get_parameter("loglevel") or "WARNING")


class EventHandler:

    @staticmethod
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
        except TypeError as err:
            logger.exception('Los valores de "NewImage" y "OldImage" deberían '
                             'ser diccionarios no-vacíos cuya key corresponde '
                             'a un tipo de dato de DynamoDB soportado por '
                             'boto3.')
            err.add_note(f'"{dynamo_db_dict}" no tiene el formato de DynamoDB')
            raise

    @staticmethod
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
            if isinstance(v, dict):
                cambios[k] = EventHandler.obtener_cambios(new_dict.get(k, {}),
                                                          v)
            elif v != new_dict.get(k) and k != "updated_at":
                cambios[k] = new_dict.get(k)
        cambios |= {k: v for k, v in new_dict.items() if k not in old_dict}
        return cambios

    @staticmethod
    def formatear_evento(evento: dict) -> tuple[dict | None]:
        """Recibe el evento y lo formatea, regresando la imagen anterior
        y los cambios realizados de la data enviada por la base de datos
        para su posterior manipulación.

        Args:
            evento (dict): Evento mandado por una acción de DynamoDB.

        Returns:
            tuple[dict]: Tupla con los diccionarios deserealizados de los
            cambios registrados por el evento y la imagen previa a los cambios.
        """
        try:
            new_image = EventHandler.deserializar(
                evento['dynamodb']['NewImage']
            )
            old_image = EventHandler.deserializar(
                evento['dynamodb'].get('OldImage', {})
            )
            cambios = EventHandler.obtener_cambios(new_image, old_image)
            logger.debug(f'{cambios = }')
            return old_image, cambios
        except KeyError:
            logger.exception("Formato inesperado para el evento.\n"
                             "El evento debería tener los objetos\n"
                             '{\n\t...,\n\t"dynamobd": {\n\t\t...\n\t\t'
                             '"NewImage": ...\n\t}\n}')
            raise

    def __init__(self, evento: dict, handler_mapping: dict[str, ItemHandler]):
        """Constructor de la instancia encargada de procesar el evento

        Args:
            evento (dict): Evento accionado por DynamoDB.
        """
        self.event_name = evento['eventName']
        self.old_image, self.cambios = (
            EventHandler.formatear_evento(evento)
        )
        self.handler_mapping = handler_mapping

    @property
    def handler(self) -> ItemHandler:
        """Obtiene un handler para el evento según el entity del ítem que
        provocó el evento.

        Returns:
            ItemHandler: El manipulador adecuado para el evento del
            registro.
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
        try:
            r = self.handler(self).ejecutar()
            return {"status": "OK", "respuesta": r}
        except Exception:
            logger.exception("Ocurrió un error ejecutando el evento.")
            raise


def procesar_todo(service_name: str, evento: list[dict],
                  handler_mapping: dict[str, ItemHandler]):
    eventos_en_cola = obtener_eventos_en_cola(service_name=service_name,
                                              evento_nuevo=evento)
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
            msg = (f"Ocurrió un error manejado el evento:\n{ev}."
                   f"Se levantó la excepción '{err}'.")
            logger.exception(msg)
            if n == 0:
                raise Exception(msg) from err
            continue
        else:
            evento.borrar_de_cola()

    return r
