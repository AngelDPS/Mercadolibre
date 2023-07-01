import json
import boto3
from aws_lambda_powertools import Logger
from libs.util import obtener_codigo, get_parameter

logger = Logger(service="sqs_handler",
                level=get_parameter("loglevel") or "WARNING")
sqs_client = boto3.client("sqs")


def _receive_messages(sqs_url: str) -> list[dict]:
    """Consulta los mensajes en la cola de SQS que resultaron de un error
    al manejar el evento.

    Returns:
        list[dict]: Lista con todos los mensajes en cola en SQS.
    """
    response = sqs_client.receive_message(
        QueueUrl=sqs_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=1,
    )
    logger.info(f"Se recibieron {len(response.get('Messages', []))} "
                "eventos NO procesados en cola.")
    return response


class EventoEnCola:

    def __init__(self, contenido: list[dict],
                 receipt_handle: str = "",
                 sqs_url: str = ""):
        self.contenido = contenido
        self.ids = [receipt_handle] if receipt_handle else []
        self.sqs_url = sqs_url or None
        self.codigo = obtener_codigo(contenido)

    def __eq__(self, other):
        if isinstance(other, EventoEnCola):
            return self.codigo == other.codigo
        else:
            False

    def __str__(self):
        return str(self.contenido)

    def borrar_de_cola(self, only_last: bool = False):
        if self.sqs_url is not None:
            if only_last:
                sqs_client.delete_message(
                    QueueUrl=self.sqs_url,
                    ReceiptHandle=self.ids.pop(),
                )
            else:
                [sqs_client.delete_message(
                    QueueUrl=self.sqs_url,
                    ReceiptHandle=id,
                ) for id in self.ids]

    def unir_eventos(self, other):
        if self == other:
            while len(self.ids) >= 2:
                logger.info("El evento ya se había repetido, "
                            "se eliminará el mensaje repetido anterior.")
                self.borrar_de_cola(only_last=True)
            self.contenido[0]["dynamodb"]["NewImage"] = (
                other.contenido[0]["dynamodb"]["NewImage"]
            )
            self.ids.extend(other.ids)


def obtener_eventos_en_cola(
    service_name: str,
    evento_nuevo: list[dict]
) -> dict[str, EventoEnCola]:
    """Usando el `service_name`, consulta el parameter store por el campo
    {SERVICE_NAME}_SQSURL, con este se consulta la cola de mensajes con eventos
    no-procesados, y se analizan por casos de repeticiones entre si mismos y
    `evento`.

    Args:
        service_name (str): Nombre del servicio para formar el campo
        {SERVICE_NAME}_URL del parámetro en el parameter store.
        evento (list[dict]): Evento para agregar al final del diccionario,
        analizando por repetición.

    Returns:
        dict[str, EventoEnCola]:
    """
    param_key = f"{service_name.upper()}_SQSURL"
    sqs_url = get_parameter(param_key)
    if sqs_url is None:
        raise ValueError(
            f"""No se encontró el valor para {param_key} en el parámetro
            consultado.
            Asegúrese que el parámetro esté configurado correctamente.
            """
        )

    cola = []

    for n, mensaje in enumerate(
            _receive_messages(sqs_url).get("Messages", [])
    ):
        evento_q = EventoEnCola(
            contenido=json.loads(mensaje["Body"]),
            receipt_handle=mensaje['ReceiptHandle'],
            sqs_url=sqs_url
        )
        logger.debug(f"Evento {n+1} = {evento_q}")

        if not evento_q.codigo:
            logger.info(
                f"El evento {n+1} en cola corresponde a una entidad "
                "cuyo proceso no está implementado y se eliminará.")
            evento_q.borrar_de_cola()
            continue

        if evento_q in cola:
            logger.info(
                f"Evento {n+1} repetido en la cola para {evento_q.codigo}"
            )
            cola[cola.index(evento_q)].unir_eventos(evento_q)
        else:
            cola.append(evento_q)

    evento_nuevo = EventoEnCola(evento_nuevo)
    if evento_nuevo in cola:
        logger.warning(
            f'Se encontraron eventos en cola para para "{evento_nuevo.codigo}"'
            ' siendo procesado.'
        )
        idx = cola.index(evento_nuevo)
        cola[idx].unir_eventos(evento_nuevo)
        cola.insert(0, cola.pop(idx))
    else:
        cola.insert(0, evento_nuevo)

    return cola
