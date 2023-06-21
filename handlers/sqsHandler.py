import json
import boto3
from logging import getLogger
from libs.util import obtener_codigo, get_parameter

logger = getLogger(__name__)
sqs_client = boto3.client("sqs")


class SQShandler:

    def __init__(self, service_name: str):
        param_key = f"{service_name.upper()}_SQSURL"
        self.SQSURL = get_parameter(param_key)
        if self.SQSURL is None:
            raise ValueError(
                f"""No se encontró el valor para {param_key} en el parámetro
                consultado.
                Asegúrese que el parámetro esté configurado correctamente.
                """
            )

    def _receive_messages(self):
        response = sqs_client.receive_message(
            QueueUrl=self.SQSURL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=1,
        )
        logger.info(f"Se recibieron {len(response.get('Messages', []))} "
                    "eventos NO procesados en cola.")
        return response

    def delete_message(self, id_recepcion):
        sqs_client.delete_message(
            QueueUrl=self.SQSURL,
            ReceiptHandle=id_recepcion,
        )

    @staticmethod
    def procesar_entidades_repetidas(codigo, lista_codigos, eventos, NewImage):
        if codigo in lista_codigos:
            idx = lista_codigos.index(codigo)
            eventos[idx][0]["dynamodb"]["NewImage"] = NewImage
            return idx
        else:
            return None

    def process_messages(self):
        eventos = []
        ids = []
        codigos_vistos = []
        codigos_repetidos = {}

        for n, mensaje in enumerate(
                self.receive_messages().get("Messages", [])
        ):
            id_recepcion = mensaje['ReceiptHandle']
            evento = json.loads(mensaje["Body"])
            logger.debug(f"Evento {n+1} = {evento}")
            codigo = obtener_codigo(evento)

            if not codigo:
                logger.info(
                    f"El evento {n+1} en cola corresponde a una entidad "
                    "cuyo proceso no está implementado y se eliminará.")
                self.delete_message(id_recepcion)
                continue

            if codigo in codigos_vistos:
                logger.info(
                    f"Evento {n+1} repetido en la cola para {codigo = }")
                if codigo in codigos_repetidos:
                    logger.info("El evento ya se había repetido, "
                                "se eliminará el mensaje repetido anterior.")
                    self.delete_message(
                        codigos_repetidos[codigo]["ReceiptHandle"]
                    )
                codigos_repetidos[codigo] = {
                    "NewImage": evento[0]["dynamodb"]["NewImage"],
                    "ReceiptHandle": id_recepcion
                }
            else:
                codigos_vistos.append(codigo)
                eventos.append(evento)
                ids.append(id_recepcion)

        for codigo, codigo_dict in codigos_repetidos.items():
            self.procesar_entidades_repetidas(codigo, codigos_vistos, eventos,
                                              codigo_dict["NewImage"])

        logger.debug(f'Eventos procesados de la cola = {eventos}')
        return eventos, ids, codigos_vistos, codigos_repetidos
