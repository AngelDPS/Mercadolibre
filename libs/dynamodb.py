import boto3
from botocore.exceptions import ClientError
from os import environ

dynamodb = boto3.resource("dynamodb")
# TODO: Aquí se obtiene y usa el parámetro de configuración para la base de
# datos de DynamoDB.
tabla = dynamodb.Table(environ["DYNAMODB_TABLE"])


def guardar_MeliIdArticulo(PK: str, SK: str, ID: str):
    tabla.update_item(
        Key={"PK": PK, "SK": SK},
        UpdateExpression="SET meliID = :ID",
        ExpressionAttributeValues={":ID": ID}
    )


def obtener_MeliAccessToken(codigoCompania: str,
                            codigoTienda: str) -> str:
    key = {
        "PK": f"{codigoCompania.upper()}#TIENDAS",
        "SK": f"T#{codigoTienda.upper()}"
    }
    return tabla.get_item(
        Key=key,
        ProjectionExpression="meLi.token"
    )['Item']


def guardar_MeliAccessToken(codigoCompania: str,
                            codigoTienda: str,
                            token: str):
    key = {
        "PK": f"{codigoCompania.upper()}#TIENDAS",
        "SK": f"T#{codigoTienda.upper()}"
    }
    try:
        tabla.update_item(
            Key=key,
            UpdateExpression="SET meLi.token = :token",
            ExpressionAttributeValues={
                ":token": token
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
    return tabla.get_item(
        Key=key,
        ProjectionExpression="meLi.client"
    )['Item']
