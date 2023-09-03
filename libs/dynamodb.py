import boto3
from botocore.exceptions import ClientError
from os import getenv
import time
from decimal import Decimal
from aws_lambda_powertools import Logger

logger = Logger(child=True)


def obtener_tabla():
    if getenv("AWS_EXECUTION_ENV") is None:
        session = boto3.Session(profile_name=getenv("AWS_PROFILE_NAME"))
    else:
        session = boto3
    return (
        session.resource("dynamodb").Table(f"{getenv('NOMBRE_COMPANIA')}-db")
    )


def guardar_articulo_meli_id(PK: str, SK: str, ID: str):
    obtener_tabla().update_item(
        Key={"PK": PK, "SK": SK},
        UpdateExpression="SET meli_id = :ID",
        ExpressionAttributeValues={":ID": ID}
    )


def guardar_meli_error(PK: str, SK: str, cause_msg: list):
    obtener_tabla().update_item(
        Key={"PK": PK, "SK": SK},
        UpdateExpression="SET meli_error = :msg",
        ExpressionAttributeValues={":msg": cause_msg}
    )


def obtener_meli_access_token(codigo_compania: str,
                              codigo_tienda: str) -> dict:
    key = {
        "PK": f"{codigo_compania.upper()}#TIENDAS",
        "SK": f"T#{codigo_tienda.upper()}"
    }
    return obtener_tabla().get_item(
        Key=key,
        ProjectionExpression="meli.refresh_token"
    )['Item']['meli']['refresh_token']


def guardar_meli_access_token(codigo_compania: str,
                              codigo_tienda: str,
                              token: dict):
    token["expires_at"] = Decimal(time.time() + 18000)
    logger.debug(f"Guardando access token en DynamoDB: {token}")
    key = {
        "PK": f"{codigo_compania.upper()}#TIENDAS",
        "SK": f"T#{codigo_tienda.upper()}"
    }
    try:
        tabla = obtener_tabla()
        tabla.update_item(
            Key=key,
            UpdateExpression="SET meli.refresh_token = :refresh_token",
            ExpressionAttributeValues={
                ":refresh_token": token
            }
        )
    except ClientError as err:
        if err.response['Error']['Code'] == 'ValidationException':
            tabla.update_item(
                Key=key,
                UpdateExpression="SET meli = :dict",
                ExpressionAttributeValues={
                    ":dict": {
                        "token": token
                    }
                }
            )
        else:
            raise


def obtener_meli_client_credentials(codigo_compania: str,
                                    codigo_tienda: str) -> dict[str, str]:
    key = {
        "PK": f"{codigo_compania.upper()}#TIENDAS",
        "SK": f"T#{codigo_tienda.upper()}"
    }
    client = obtener_tabla().get_item(
        Key=key,
        ProjectionExpression="meli.client"
    )
    return client['Item'].get("meli", {}).get("client", {})


def obtener_articulo(codigo_compania: str, codigo_tienda: str,
                     co_art: str) -> dict:
    PRIMARY_KEY = (
        f"{codigo_compania.upper()}#{codigo_tienda.upper()}#{co_art.upper()}"
    )
    return obtener_tabla().get_item(
        Key={"PK": PRIMARY_KEY, "SK": "METADATA"}
    )['Item']


def borrar_articulo_meli_id(codigo_compania: str, codigo_tienda: str,
                            co_art: str):
    PRIMARY_KEY = (
        f"{codigo_compania.upper()}#{codigo_tienda.upper()}#{co_art.upper()}"
    )
    return obtener_tabla().update_item(
        Key={"PK": PRIMARY_KEY, "SK": "METADATA"},
        UpdateExpression="REMOVE meli_id"
    )
