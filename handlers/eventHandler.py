from boto3.dynamodb.types import TypeDeserializer
from libs.util import ItemHandler, get_parameter
from aws_lambda_powertools import Logger

logger = Logger(service="event_handler",
                level=get_parameter("loglevel") or "WARNING")


class EventHandler:

    @staticmethod
    def deserializar(Image: dict) -> dict:
        """Deserializa un diccionario serializado segun DynamoDB

        Args:
            Image (dict): Diccionario serializado segun DynamoDB

        Returns:
            dict: Diccionario deserealizado
        """
        deserializer = TypeDeserializer()
        try:
            return {k: deserializer.deserialize(v) for k, v in Image.items()}
        except TypeError as err:
            logger.exception('Los valores de "NewImage" y "OldImage" deberían '
                             'ser diccionarios no-vacíos cuya key corresponde '
                             'a un tipo de dato de DynamoDB soportado por '
                             'boto3.')
            err.add_note(f'"{Image}" no tiene el formato de DynamoDB')
            raise

    @staticmethod
    def obtenerCambios(NewImage: dict, OldImage: dict) -> dict:
        """Obtiene los cambios realizados entre dos diccionarios, con
        versiones posterior y previa.
        Los cambios se obtienen de forma recursiva. Es decir, se obtienen los
        cambios entre los diccionarios principales y los diccionarios anidados
        en los mismos.

        Args:
            NewImage (dict): Diccionario con data posterior.
            OldImage (dict): Diccionario con data previa.

        Returns:
            dict: Diccionario con las entradas que fueron modificadas entre las
            versiones, con los valores del diccionario posterior.
        """
        cambios = {}
        for k, v in OldImage.items():
            if isinstance(v, dict):
                cambios[k] = EventHandler.obtenerCambios(NewImage.get(k, {}),
                                                         v)
            elif v != NewImage.get(k) and k != "updated_at":
                cambios[k] = NewImage.get(k)
        cambios |= {k: v for k, v in NewImage.items() if k not in OldImage}
        return cambios

    @staticmethod
    def formatearEvento(evento: dict) -> tuple[dict]:
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
            NewImage = EventHandler.deserializar(
                evento['dynamodb']['NewImage']
            )
            OldImage = EventHandler.deserializar(
                evento['dynamodb'].get('OldImage', {})
            )
            cambios = EventHandler.obtenerCambios(NewImage, OldImage)
            logger.debug(f'{cambios = }')
            return cambios, OldImage
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
        self.cambios, self.OldImage = self.formatearEvento(evento)
        self.handler_mapping = handler_mapping

    @property
    def handler(self) -> ItemHandler:
        """Obtiene un handler para el evento según el entity del ítem que
        provocó el evento.

        Returns:
            ProductoHandler: El manipulador adecuado para el evento del
            registro.
        """
        try:
            handler = self.handler_mapping[self.OldImage.get('entity')
                                           or self.cambios.get('entity')]
            logger.info(f"El evento será procesado por {handler}.")
            return handler
        except KeyError as err:
            raise NotImplementedError(
                "El evento corresponde a una entidad de "
                f"{self.OldImage.get('entity') or self.cambios.get('entity')}"
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
            return {"status": "OK", "respuestas": r}
        except Exception:
            logger.exception("Ocurrió un error ejecutando el evento.")
            raise
