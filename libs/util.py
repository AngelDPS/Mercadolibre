from aws_lambda_powertools.utilities import parameters
from os import getenv
from logging import getLogger
from typing import Any

logger = getLogger(__name__)


def obtener_codigo(evento):
    match evento[0]["dynamodb"]["NewImage"]["entity"]["S"]:
        case "articulos":
            return evento[0]["dynamodb"]["NewImage"]["co_art"]["S"]
        case _:
            return None


def get_parameter(key: str) -> Any:
    try:
        parameter = f"/akia9/akiastock/{getenv('NOMBRE_COMPANIA')}"
        return parameters.get_parameter(parameter, transform="json",
                                        max_age=300).get(key)
    except Exception:
        logger.exception(
            f"Ocurrión un error obteniendo el valor de '{key}' del "
            f"parámetro '{parameter}'.")
        raise
