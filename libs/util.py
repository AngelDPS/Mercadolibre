from aws_lambda_powertools.utilities.parameters import SSMProvider
from boto3 import Session
from os import getenv
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any
from aws_lambda_powertools import Logger

logger = Logger(service="utilities")


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
    if getenv("AWS_EXECUTION_ENV") is None:
        ssm_provider = SSMProvider(
            boto3_session=Session(profile_name=getenv('AWS_PROFILE_NAME'))
        )
    else:
        ssm_provider = SSMProvider()
    return ssm_provider.get(
        f"/akia9/akiastock/{getenv('NOMBRE_COMPANIA')}",
        transform="json",
        max_age=300
    ).get(key)


def obtener_codigo(record: dict) -> str | None:
    """Obtiene el código identificador de la entidad del ítem de DynamoDB
    que generó el record.

    Args:
        record (dict): Evento recibido por Lambda para ser procesado
        debido a cambios en DynamoDB.

    Returns:
        str | None: Código  único del ítem de DynamoDB para la entidad.
    """
    try:
        new_image = record["dynamodb"]["NewImage"]
    except KeyError:
        new_image = record["Records"][0]["dynamodb"]["NewImage"]
    except IndexError:
        new_image = record[0]["dynamodb"]["NewImage"]
    match new_image["entity"]["S"]:
        case "articulos":
            return new_image["co_art"]["S"]
        case "lineas":
            return new_image["co_lin"]["S"]
        case "tiendas":
            return new_image["codigoTienda"]["S"]
        case _:
            return None


class ItemHandler(ABC):
    ITEM_TYPE: str
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
                            f"{self.ITEM_TYPE} en {web_store}.")
                if not self.old_image.dict(exclude_unset=True):
                    logger.info(
                        "Al no haber OldImage en el evento, se identica "
                        "como un INSERT y se procede a crear el "
                        f"{self.ITEM_TYPE} en {web_store}."
                    )
                    respuesta = self.crear()
                elif not id:
                    self.cambios = self.cambios.parse_obj(
                        self.old_image.dict()
                        | self.cambios.dict(exclude_unset=True)
                    )
                    logger.info(
                        "En el evento, proveniente de la base de "
                        "datos, no se encontró el ID de "
                        f"{self.ITEM_TYPE} para {web_store}. Se creará un "
                        f"{self.ITEM_TYPE} nuevo con la data actualizada."
                    )
                    respuesta = self.crear()
                else:
                    respuesta = self.modificar()
            else:
                logger.info("Los cambios encontrados no ameritan "
                            f"actualizaciones en {web_store}.")
                respuesta = {
                    "statusCode": 200,
                    "body": "No se realizaron cambios"
                }
        except Exception:
            logger.info("Ocurrió un problema ejecutando la acción "
                        "sobre el producto.")
            raise
        return respuesta


def filtro_campos_completos(evento):
    filtro_campos = [
        "prec_vta1", "prec_vta2", "prec_vta3", "PK", "SK", "habilitado",
        "art_des", "codigoCompania", "codigoTienda", "co_art", "co_lin",
        "stock_act", "stock_com", "imagen_url"
    ]

    try:
        ev = evento["Records"][0]
    except IndexError:
        ev = evento[0]

    if ev.get("eventName") == "INSERT":
        for key in filtro_campos:
            if key not in ev["dynamodb"]["NewImage"]:
                logger.error("El evento no contiene el campo " + key)
                raise ValueError("El evento no contiene el campo " + key)
    elif ev.get("eventName") == "MODIFY":
        for key in filtro_campos:
            if (key not in ev["dynamodb"]["NewImage"]
                    or key not in ev["dynamodb"]["OldImage"]):
                logger.error("El evento no contiene el campo " + key)
                raise ValueError("El evento no contiene el campo " + key)
    else:
        logger.error("El evento no es válido", evento)
        raise ValueError("El evento no es válido")
