import boto3
from botocore.exceptions import ClientError
from os import getenv
from logging import getLogger

dynamodb = boto3.resource("dynamodb")
tabla = dynamodb.Table(f"{getenv('NOMBRE_COMPANIA')}-db")
logger = getLogger("meli.dynamodb")


def guardar_MeliIdArticulo(PK: str, SK: str, ID: str):
    tabla.update_item(
        Key={"PK": PK, "SK": SK},
        UpdateExpression="SET meli_ID = :ID",
        ExpressionAttributeValues={":ID": ID}
    )


def obtener_MeliAccessToken(codigoCompania: str,
                            codigoTienda: str) -> dict:
    key = {
        "PK": f"{codigoCompania.upper()}#TIENDAS",
        "SK": f"T#{codigoTienda.upper()}"
    }
    return tabla.get_item(
        Key=key,
        ProjectionExpression="meli.refresh_token"
    )['Item']['meli']['refresh_token']


def guardar_MeliAccessToken(codigoCompania: str,
                            codigoTienda: str,
                            token: dict):
    key = {
        "PK": f"{codigoCompania.upper()}#TIENDAS",
        "SK": f"T#{codigoTienda.upper()}"
    }
    try:
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
                UpdateExpression="SET meLi = :dict",
                ExpressionAttributeValues={
                    ":dict": {
                        "token": token
                    }
                }
            )
        else:
            raise


def obtener_MeliClientCredentials(codigoCompania: str,
                                  codigoTienda: str) -> dict[str, str]:
    key = {
        "PK": f"{codigoCompania.upper()}#TIENDAS",
        "SK": f"T#{codigoTienda.upper()}"
    }
    client = tabla.get_item(
        Key=key,
        ProjectionExpression="meli.client"
    )
    return client['Item'].get("meli", {}).get("client", {})
