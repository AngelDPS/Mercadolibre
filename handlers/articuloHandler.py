from libs.dynamodb import guardar_articulo_meli_id
from models.articulo import (
    MArticuloInput,
    Attributes,
    Shipping
)
from models.evento import MArticuloMeli as MArticulo
from libs.conexion import MeliConexion
from libs.util import get_parameter, ItemHandler
from re import search
import requests
import boto3
from enum import Enum
from aws_lambda_powertools import Logger

logger = Logger(child=True)


def get_url(fname: str) -> str:
    s3_client = boto3.client(
        's3', region_name='us-east-2',
        config=boto3.session.Config(signature_version='s3v4')
    )
    return s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': get_parameter("bucketname"),
                'Key': f"imagenes/{fname}"},
        ExpiresIn=3600
    )


class Habilitado(Enum):
    ACTIVE = 1
    PAUSED = 0


class TipoPublicacion(Enum):
    FREE = "free"
    GRATIS = "free"
    BRONZE = "bronze"
    BASICO = "bronze"
    BÁSICO = "bronze"
    GOLD_SPECIAL = "gold_special"
    PREMIUM = "gold_special"


class ArticuloHandler(ItemHandler):

    def __init__(self, evento):
        """Constructor de la clase

        Args:
            NewImage (MArticulo): Imagen de la base de datos para artículos
            con el artículo a crear (para INSERT) o con la data actualizada
            (para MODIFY).
            old_image (MArticulo, optional): En caso de MODIFY, la imagen
            previa a las actualizaciones. Defaults to None.
            cambios (MArticulo, optional): En caso de MODIFY, los cambios
            encontrados en los campos entre la imagen nueva y vieja.
            Defaults to None.
        """
        if not (evento.old_image.get('meli_habilitado') or
                evento.cambios.get('meli_habilitado')):
            logger.info(
                """El articulo no está habilitado para MercadoLibre y será
                ignorado.
                Para cambiar esto, establezca el registro meli.habilitado
                con el valor '1'."""
            )
            self.procesar = False
        else:
            self.procesar = True

            campo_precio = get_parameter('MELI_PRECIO')

            self.cambios = evento.cambios
            self.cambios.pop('meli_id', None)
            if campo_precio in self.cambios:
                self.cambios['precio'] = self.cambios[campo_precio]
            if ('habilitado' in self.cambios
                    or 'meli_habilitado' in self.cambios):
                self.cambios['habilitado'] = Habilitado(
                    self.cambios.get('habilitado',
                                     evento.old_image.get('habilitado')) and
                    self.cambios.get('meli_habilitado',
                                     evento.old_image.get('meli_habilitado')
                                     )
                ).name.lower()
            if 'meli_tipo_publicacion' in self.cambios:
                self.cambios['meli_tipo_publicacion'] = TipoPublicacion[
                    self.cambios['meli_tipo_publicacion'].upper()
                ].value
            self.cambios = MArticulo.parse_obj(self.cambios)

            self.old_image = evento.old_image
            if self.old_image:
                self.old_image['precio'] = self.old_image[campo_precio]
                self.old_image['habilitado'] = Habilitado(
                    self.old_image.get('habilitado') and
                    self.old_image.get('meli_habilitado')
                ).name.lower()
                self.old_image['meli_tipo_publicacion'] = TipoPublicacion[
                    self.old_image.get('meli_tipo_publicacion', 'free').upper()
                ].value
            self.old_image = MArticulo.parse_obj(self.old_image)

            self.session = MeliConexion(
                self.old_image.codigoCompania or self.cambios.codigoCompania,
                self.old_image.codigoTienda or self.cambios.codigoTienda
            )

    def dynamo_guardar_meli_id(self):
        """Actualiza el ID de MercadoLibre para el articulo usando la
        información guardada en la instancia.
        """
        logger.debug(f"MeLi ID de artículo: {self.old_image.meli_id}")
        guardar_articulo_meli_id(
            PK=self.old_image.PK or self.cambios.PK,
            SK=self.old_image.SK or self.cambios.SK,
            ID=self.old_image.meli_id
        )

    @staticmethod
    def _procesar_imagen(f_name: str):
        pattern = r"\.(jpg|jpeg|png|gif|webp)$"
        try:
            f_extension = search(pattern, f_name)[1]
        except IndexError or TypeError:
            raise ValueError("El tipo de archivo usado no tiene soporte. "
                             "Tipos de archivo válidos son "
                             "[jpg, jpeg, png, gif, webp].")
        mime_type = ("image/jpeg" if f_extension == "jpg"
                     else f"image/{f_extension}")
        url = get_url(f_name)
        imagen = requests.get(url).content
        return {'file': (f_name, imagen, mime_type)}

    def _cargar_imagen(self, file):
        try:
            files = self._procesar_imagen(file)
            r = self.session.post('pictures/items/upload', files=files)
            img_id = r.json()['id']
            return img_id
        except ValueError as err:
            logger.exception(err)
            logger.warning(f"El tipo de imagen de '{file}' no tiene soporte en"
                           " MeLi y se saltará su carga.")
            return None
        except Exception as err:
            logger.exception(err)
            logger.warning(f"No se pudo asociar '{file}' al artículo.")
            try:
                return img_id
            except NameError:
                logger.warning("Hubo problemas cargando la imagen a "
                               "MercadoLibre.")
                return None

    def _obtener_atributos(self):
        attr_from_entry = {
            'GTIN': 'codigo_barra',
            'SELLER_SKU': 'referencia',
            'BRAND': 'marca',
            'MODEL': 'modelo'
        }
        atributos = [(id, getattr(self.cambios, registro, None))
                     for id, registro in attr_from_entry.items()]
        atributos = [Attributes(id=id, value_name=value)
                     for id, value in atributos if value is not None]
        return atributos or None

    def _crear(self):
        articulo_input = MArticuloInput(
            **self.cambios.dict(by_alias=True,
                                exclude_none=True),
            available_quantity=(self.cambios.stock_act
                                - self.cambios.stock_com),
            sale_terms=None,
            pictures=[
                {'id': imgID}
                for imgID in self.old_image.meli_id['imagenes'].values()
            ],
            attributes=self._obtener_atributos(),
            shipping=Shipping()
        ).dict(exclude_none=True)
        logger.debug(articulo_input)
        response = self.session.post(
            'items',
            json=articulo_input
        )
        id_dict = {
            'articulo': response.json()['id']
        }
        return id_dict

    def _agregar_descripcion(self):
        self.session.post(
            f'items/{self.old_image.meli_id["articulo"]}/description',
            json={'plain_text': (self.cambios.meli_descripcion
                                 or "Sin descripción.")}
        )

    def _establecer_estatus(self):
        self.session.put(
            f'items/{self.old_image.meli_id["articulo"]}',
            json={'status': self.cambios.habilitado}
        )

    def crear(self) -> list[str]:
        """Función dedicada a crear un producto en Shopify dada
        la información de un evento de artículo INSERT

        Returns:
            str: Respuesta dada una operación exitosa.
        """
        logger.info("Creando artículo para MercadoLibre.")
        logger.debug(self.cambios.dict())
        try:
            self.old_image.meli_id |= {'imagenes': {
                img: self._cargar_imagen(img)
                for img in self.cambios.imagen_url
            }}
            self.old_image.meli_id |= self._crear()
            self._agregar_descripcion()
            self._establecer_estatus()
            self.dynamo_guardar_meli_id()
            return ["Producto creado!"]
        except Exception:
            logger.exception("No fue posible crear el producto.")
            raise

    def _modificar_descripcion(self):
        if "meli_descripcion" in self.cambios.dict(exclude_unset=True):
            r = self.session.put(
                f'items/{self.old_image.meli_id["articulo"]}/description',
                json={'plain_text': self.cambios.meli_descripcion
                      or "Sin descripción."}
            )
            r.raise_for_status()
            return "Descripción modificada."
        else:
            return "Descripción no modificada."

    def _obtener_imagenes(self):
        urls_anexados = list(
            set(self.cambios.imagen_url) - set(self.old_image.imagen_url)
        )
        self.old_image.meli_id['imagenes'] |= {
            img: self._cargar_imagen(img)
            for img in urls_anexados
        }
        if "imagen_url" in self.cambios.dict(exclude_unset=True):
            return [
                {'id': self.old_image.meli_id['imagenes'][fname]}
                for fname in self.cambios.imagen_url
            ]
        else:
            return None

    def _cambio_cantidad(self):
        stock_new = ((self.cambios.stock_act or self.old_image.stock_act)
                     - (self.cambios.stock_com or self.old_image.stock_com))
        stock_old = (self.old_image.stock_act - self.old_image.stock_com)
        if stock_new != stock_old:
            return stock_new
        else:
            return None

    def _modificar_articulo(self):
        articulo_input = MArticuloInput(
            **self.cambios.dict(exclude_unset=True),
            available_quantity=self._cambio_cantidad(),
            pictures=self._obtener_imagenes(),
            attributes=self._obtener_atributos()
        ).dict(exclude_none=True, exclude_unset=True)
        logger.debug(articulo_input)
        if articulo_input:
            response = self.session.put(
                f'items/{self.old_image.meli_id["articulo"]}',
                json=articulo_input
            )
            response.raise_for_status()
            return "Producto Modificado"
        else:
            return "Producto no modificado."

    def modificar(self) -> list[str]:
        logger.debug(f"{self.cambios = }")
        logger.debug(f"{self.old_image = }")
        try:
            respuestas = []
            respuestas.append(self._modificar_descripcion())
            respuestas.append(self._modificar_articulo())
            return respuestas
        except Exception:
            logger.exception("No fue posible modificar el producto.")
            raise

    def ejecutar(self) -> list[str]:
        """Ejecuta la acción requerida por el evento procesado en la instancia.

        Returns:
            list[str]: Conjunto de resultados obtenidos por las operaciones
            ejecutadas.
        """
        if self.procesar:
            respuesta = super().ejecutar("MercadoLibre",
                                         self.old_image.meli_id)
        else:
            logger.info("El artículo no está habilitado para procesarse en "
                        "MercadoLibre.")
            respuesta = ["Artículo inhabilitado."]

        return respuesta
