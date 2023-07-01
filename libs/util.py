from aws_lambda_powertools.utilities import parameters
from os import getenv
from logging import getLogger
from typing import Any
from abc import ABC, abstractmethod
from pydantic import BaseModel

logger = getLogger(__name__)


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
        case _:
            return None


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
    try:
        parameter = f"/akia9/akiastock/{getenv('NOMBRE_COMPANIA')}"
        return parameters.get_parameter(parameter, transform="json",
                                        max_age=300).get(key)
    except Exception:
        logger.exception(
            f"Ocurrión un error obteniendo el valor de '{key}' del "
            f"parámetro '{parameter}'.")
        raise


class ItemHandler(ABC):
    OldImage: dict | BaseModel
    cambios: dict | BaseModel

    @abstractmethod
    def crear(self): pass

    @abstractmethod
    def modificar(self): pass

    @abstractmethod
    def ejecutar(self, web_store: str, ID: str | None) -> list[str]:
        """Ejecuta la acción requerida por el evento procesado en la instancia.

        Returns:
            list[str]: Conjunto de resultados obtenidos por las operaciones
            ejecutadas.
        """
        try:
            if self.cambios.dict(exclude_unset=True):
                logger.info(f"Se aplicarán los cambios en {web_store}.")
                if not ID:
                    logger.info(
                        "En el evento no se encontró el ID de "
                        f"{web_store} proveniente de la base de "
                        "datos. Se asume que el articulo "
                        f"correspondiente no existe en {web_store}."
                        " Se creará un articulo nuevo con la data "
                        "actualizada."
                    )
                    self.cambios = self.cambios.parse_obj(
                        self.OldImage.dict()
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
