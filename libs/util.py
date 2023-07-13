from aws_lambda_powertools.utilities import parameters
from os import getenv
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any
from aws_lambda_powertools import Logger


def get_parameter(key: str) -> Any:
    """Obtiene el valor asociado al key del json almacenado como
    parámetro "/akia9/akiastock/{NOMBRE_COMPANIA}"en el
    Parameter Store del AWS Systems Manager.

    Args:
        key (str): Key para la identificación del valor requerido del json
        almacenado en el parámetro.

    Returns:
        Any: Valor obtenido del json almacenado en el parámetro.
    """
    parameter = f"/akia9/akiastock/{getenv('NOMBRE_COMPANIA')}"
    return parameters.get_parameter(parameter, transform="json",
                                    max_age=300).get(key)


logger = Logger(service="utilities", level=get_parameter("loglevel"))


def obtener_codigo(evento: list[dict]) -> str | None:
    """Obtiene el código identificador de la entidad del ítem de DynamoDB
    que generó el evento.

    Args:
        evento (list[dict]): Evento recibido por Lambda para ser procesado
        debido a cambios en DynamoDB.

    Returns:
        str | None: Código  único del ítem de DynamoDB para la entidad.
    """
    match evento[0]["dynamodb"]["NewImage"]["entity"]["S"]:
        case "articulos":
            return evento[0]["dynamodb"]["NewImage"]["co_art"]["S"]
        case "lineas":
            return evento[0]["dynamodb"]["NewImage"]["co_lin"]["S"]
        case "tiendas":
            return evento[0]["dynamodb"]["NewImage"]["codigoTienda"]["S"]
        case _:
            return None


class ItemHandler(ABC):
    item: str
    old_image: dict | BaseModel
    cambios: dict | BaseModel

    @abstractmethod
    def __init__(self): pass

    @abstractmethod
    def crear(self): pass

    @abstractmethod
    def modificar(self): pass

    @abstractmethod
    def ejecutar(self, web_store: str, id: str | None) -> list[str]:
        """Ejecuta la acción requerida por el evento procesado en la instancia.

        Returns:
            list[str]: Conjunto de resultados obtenidos por las operaciones
            ejecutadas.
        """
        try:
            if self.cambios.dict(exclude_unset=True):
                logger.info("Se aplicarán los cambios al "
                            f"{self.item} en {web_store}.")
                if not self.old_image.dict(exclude_unset=True):
                    logger.info(
                        "Al no haber OldImage en el evento, se identica como "
                        "un INSERT y se procede a crear el "
                        f"{self.item} en {web_store}."
                    )
                    respuesta = self.crear()
                elif not id:
                    logger.info(
                        "En el evento, proveniente de la base de datos, no se "
                        f"encontró el ID de {self.item} para {web_store}. "
                        f"Se creará un {self.item} nuevo con la data "
                        "actualizada."
                    )
                    self.cambios = self.cambios.parse_obj(
                        self.old_image.dict()
                        | self.cambios.dict(exclude_unset=True)
                    )
                    respuesta = self.crear()
                else:
                    respuesta = self.modificar()
            else:
                logger.info("Los cambios encontrados no ameritan "
                            f"actualizaciones en {web_store}.")
                respuesta = ["No se realizaron acciones."]
        except Exception:
            logger.exception("Ocurrió un problema ejecutando la acción "
                             "sobre el producto.")
            raise
        return respuesta
