import json
import boto3
from aws_lambda_powertools import Logger
from libs.util import obtener_codigo
from os import getenv
from typing import Any

logger = Logger(service="sqs_handler")


def _receive_messages() -> list:
    """Consulta los mensajes en la cola de SQS que resultaron de un error
    al manejar el evento.

    Returns:
        list[dict]: Lista con todos los mensajes en cola en SQS.
    """
    sqs_url = getenv("SQSERROR_URL")
    if sqs_url is None:
        raise ValueError(
            """No se encontró el valor de "SQSERROR_URL" en las variables
            de ambiente.
            Asegúrese que el ambiente esté configurado correctamente.
            """
        )
    if getenv("AWS_EXECUTION_ENV") is None:
        session = boto3.Session(profile_name=getenv("AWS_PROFILE_NAME"))
    else:
        session = boto3
    sqs_queue = (
        session.resource('sqs', region_name="us-east-2").Queue(url=sqs_url)
    )
    messages = sqs_queue.receive_messages(
        MaxNumberOfMessages=10,
        WaitTimeSeconds=1,
    )
    logger.info(f"Se recibieron {len(messages)} eventos "
                "NO procesados en cola.")
    return messages, sqs_queue


class RecordEnCola:

    def __init__(self, mensaje=None,
                 dynamo_data: dict = None):
        if mensaje is not None:
            self.mensajes = [mensaje]
            try:
                self.contenido = json.loads(mensaje.body)[0]
            except KeyError:
                self.contenido = json.loads(mensaje.body)["Records"][0]
        else:
            self.mensajes = []
        if dynamo_data is not None:
            self.contenido = dynamo_data
        elif mensaje is None:
            raise ValueError(
                "Para crear un evento en cola hace falta un mensaje de SQS o "
                "un data stream de Dynamo."
            )
        self.codigo = obtener_codigo(self.contenido)

    def __eq__(self, other):
        if isinstance(other, RecordEnCola):
            return self.codigo == other.codigo
        else:
            False

    def __str__(self):
        return str(self.contenido)

    def borrar_de_cola(self, only_last: bool = False):
        if self.mensajes:
            if only_last:
                self.mensajes.pop().delete()
            else:
                [mensaje.delete() for mensaje in self.mensajes]

    def unir_records(self, other):
        if self == other:
            while len(self.mensajes) >= 2:
                logger.info("El evento ya se había repetido, "
                            "se eliminará el mensaje repetido anterior.")
                self.borrar_de_cola(only_last=True)
            self.contenido["dynamodb"]["NewImage"] = (
                other.contenido["dynamodb"]["NewImage"]
            )
            self.mensajes.extend(other.mensajes)


def obtener_records_en_cola(record_nuevo: dict
                            ) -> tuple[list[RecordEnCola], Any]:
    """.

    Args:
        service_name (str): Nombre del servicio para formar el campo
        {SERVICE_NAME}_URL del parámetro en el parameter store.
        record_nuevo (dict): Evento para agregar al final del diccionario,
        analizando por repetición.

    Returns:
        tuple[list[RecordEnCola], Any]:
    """
    messages, sqs_queue = _receive_messages()
    cola = [RecordEnCola(mensaje=msj) for msj in messages]
    for idx, evento in enumerate(cola):
        logger.debug(f"Evento {idx+1} = {evento}")

        if not evento.codigo:
            logger.info(
                f"El evento {idx+1} en cola corresponde a una entidad "
                "cuyo proceso no está implementado y se eliminará.")
            evento.borrar_de_cola()
            del cola[idx]
            continue

        first_idx = cola.index(evento)
        if idx != first_idx:
            logger.info(
                f"Evento {idx+1} repetido en la cola para {evento.codigo}"
            )
            cola[first_idx].unir_records(evento)
            del cola[idx]

    record_nuevo = RecordEnCola(dynamo_data=record_nuevo)
    if record_nuevo in cola:
        logger.warning(
            f'Se encontraron eventos en cola para para "{record_nuevo.codigo}"'
            ' siendo procesado.'
        )
        idx = cola.index(record_nuevo)
        cola[idx].unir_records(record_nuevo)
        cola.insert(0, cola.pop(idx))
    else:
        cola.insert(0, record_nuevo)

    return cola, sqs_queue
