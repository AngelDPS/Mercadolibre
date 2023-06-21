from boto3.dynamodb.types import TypeDeserializer
from handlers.articuloHandler import (
    ArticuloHandler as meli_ArticuloHandler
)
from logging import getLogger

logger = getLogger(__name__)


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
    def formatearEvento(evento: dict) -> tuple[dict | None]:
        """Recibe el evento y lo formatea, regresando las imágenes
        (Old y New) de la data enviada por la base de datos para su posterior
        manipulación.

        Args:
            evento (dict): Evento mandado por una acción de DynamoDB.

        Returns:
            tuple[Mimage | None]: Tupla con las imágenes modeladas de la base
            de datos, New y Old, deserealizadas. En caso de no haber OldImage
            el segundo valor es igual a None.
        """
        try:
            resultado = evento['dynamodb']
            resultado['NewImage'] = EventHandler.deserializar(
                resultado['NewImage']
            )
            resultado['OldImage'] = EventHandler.deserializar(
                resultado.get('OldImage', {})
            )
            return resultado['NewImage'], resultado['OldImage']
        except KeyError:
            logger.exception("Formato inesperado para el evento.\n"
                             "El evento debería tener los objetos\n"
                             '{\n\t...,\n\t"dynamobd": {\n\t\t...\n\t\t'
                             '"NewImage": ...\n\t}\n}')
            raise

    @staticmethod
    def obtenerCambios(NewImage: dict, OldImage: dict) -> dict:
        """Obtiene los cambios realizados entre dos imágenes, anterior y
        posterior, de un ítem.

        Args:
            NewImage (Mimage): Modelo de los dátos de la tabla de DynamoDB
            con la imagen del ítem antes de ser modificado.
            OldImage (Mimage): Modelo de los dátos de la tabla de DynamoDB
            con la imagen del ítem modificado

        Returns:
            Mimage | None: Modelo con los campos de la base de datos que
            sufrieron cambios o None en caso de no haber ninguno
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

    def __init__(self, evento: dict):
        """Constructor de la instancia encargada de procesar el evento

        Args:
            evento (dict): Evento accionado por DynamoDB.
        """
        self.eventName = evento['eventName']
        self.NewImage, self.OldImage = self.formatearEvento(evento)
        self.cambios = self.obtenerCambios(self.NewImage, self.OldImage)
        logger.debug(f'{self.cambios = }')

    @property
    def handler(self):
        """Obtiene un manipulador según el tipo de registro que accionó el
        evento.

        Returns:
            ProductoHandler: El manipulador adecuado para el evento del
            registro.
        """
        try:
            handler = {
                'articulos': meli_ArticuloHandler,
            }
            handler = handler[self.NewImage['entity']]
            logger.info("El evento corresponde a una entidad de "
                        f"{self.NewImage['entity']} y será procesado por "
                        f"el {handler}.")
            return handler
        except KeyError as err:
            msg = ("El evento corresponde a una entidad de "
                   f"{self.NewImage['entity']}, cuyo proceso no está "
                   "implementado.")
            logger.exception(msg)
            raise NotImplementedError(msg) from err

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
