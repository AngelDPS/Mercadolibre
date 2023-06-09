import meli.libs.dynamodb as dynamodb
from logging import getLogger
from meli.models.articulo import (
    MArticulo_input,
    # SaleTerms,
    Attributes,
    # ShippingCost,
    Shipping
)
from meli.models.evento import Marticulo
from meli.conexion import MeLiConexion
from os import environ
from io import BytesIO
from re import search
from enum import Enum
import requests
import boto3

logger = getLogger(__name__)
s3_client = boto3.client('s3', region_name=environ.get("AWS_REGION"),
                         config=boto3.session.Config(signature_version='s3v4'))


class Habilitado(Enum):
    ACTIVE = 1
    PAUSED = 0


class ArticuloHandler:

    def actualizarIdBD(self):
        """Actualiza el ID de MercadoLibre para el articulo usando la
        información guardada en la instancia.
        """
        logger.debug(f"MeLi ID de artículo: {self.NewImage.meliID}")
        dynamodb.guardar_MeliIdArticulo(
            PK=self.NewImage.PK,
            SK=self.NewImage.SK,
            ID=self.NewImage.meliID
        )

    @staticmethod
    def obtenerCampoPrecio() -> str:
        """Lee el campo de precio a usar para el artículo.

        Returns:
            str: Campo de precio a usar.
        """
        try:
            # TODO: Aquí se obtiene el parámetro de configuración para el
            # campo del precio.
            return environ['MELI_PRECIO']
        except KeyError:
            logger.exception("No se encontró la variable de ambiente 'precio' "
                             "con el campo de precio que deben usar los "
                             "articulos.")
            raise

    def __init__(self, evento):
        """Constructor de la clase

        Args:
            NewImage (Marticulo): Imagen de la base de datos para artículos
            con el artículo a crear (para INSERT) o con la data actualizada
            (para MODIFY).
            OldImage (Marticulo, optional): En caso de MODIFY, la imagen
            previa a las actualizaciones. Defaults to None.
            cambios (Marticulo, optional): En caso de MODIFY, los cambios
            encontrados en los campos entre la imagen nueva y vieja.
            Defaults to None.
        """
        self.eventName = evento.eventName
        campo_precio = self.obtenerCampoPrecio()
        for label in ['NewImage', 'OldImage']:
            setattr(self, label,
                    Marticulo.parse_obj(getattr(evento, label)))
            getattr(self, label).precio = getattr(evento, label)[campo_precio]
            getattr(self, label).habilitado = Habilitado(
                getattr(self, label).habilitado and
                getattr(self, label).meli_habilitado
            ).name.lower()
        self.cambios = Marticulo.parse_obj(
            evento.obtenerCambios(self.NewImage, self.OldImage)
        )
        self.session = MeLiConexion(self.NewImage.codigoCompania)

    @staticmethod
    def _procesarImagen(file: str):
        pattern = r"(?P<fname>\w*\.(?P<ftype>jpg|jpeg|png|gif|webp))$"
        match = search(pattern, file)
        if not match:
            raise ValueError("El tipo de archivo usado no tiene soporte. "
                             "Tipos de archivo válidos son "
                             "[jpg, jpeg, png, gif, webp].")
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': environ.get("BUCKET_NAME"),
                    'Key': f"imagenes/{file}"},
            ExpiresIn=3600
        )
        imagen = BytesIO(requests.get(url).content)
        fname = match["fname"]
        mime_type = ("image/jpeg" if match['ftype'] == "jpg"
                     else f"image/{match['ftype']}")
        return fname, imagen, mime_type

    def _cargarImagen(self, file):
        try:
            files = {'file': self._procesarImagen(file)}
            r = self.session.post('pictures/items/upload', files=files)
            logger.debug(r.text)
            imgId = r.json()['id']
            self.session.post(f'items/{self.NewImage.meliID}/pictures',
                              json={'id': imgId})
            return imgId
        except ValueError as err:
            logger.exception(err)
            logger.warning(f"El tipo de imagen de '{file}' no tiene soporte en"
                           " MeLi y se saltará su carga.")
            return None
        except Exception:
            logger.warning("No se pudo asociar la imagen al artículo.")
            try:
                return imgId
            except NameError:
                logger.warning("Hubo problemas cargando la imagen a "
                               "MercadoLibre.")
                return None

    def _crear(self, articuloInput: MArticulo_input):
        id_dict = {
            'articulo': self.session.post('items',
                                          json=articuloInput).json()["id"]
        }
        self.session.post(
            f'items/{id_dict["id"]}/description',
            json={'plain_text': articuloInput.descripcion})
        return id_dict

    def crear(self) -> list[str]:
        """Función dedicada a crear un producto en Shopify dada
        la información de un evento de artículo INSERT

        Returns:
            str: Respuesta dada una operación exitosa.
        """
        logger.info("Creando producto a partir de artículo.")
        try:
            codigo_barra = Attributes(
                id="GTIN", value_name=self.NewImage.codigo_barra
            )
            sku = Attributes(
                id="seller_sku", value_name=self.NewImage.referencia
            )
            marca = Attributes(
                id="brand", value_name=self.NewImage.marca
            )
            articuloInput = MArticulo_input(
                **self.NewImage.dict(by_alias=True,
                                     exclude_none=True),
                available_quantity=(self.NewImage.stock_act
                                    - self.NewImage.stock_com),
                listing_type_id=environ["MELI_TIPO_PUB"],
                sale_terms=None,
                pictures=None,
                attributes=[codigo_barra, sku, marca],
                shipping=Shipping()
            )
            self.NewImage.meliID = self._crear(articuloInput)
            self.NewImage.meliID["imagenes"] = {
                img: self._cargarImagen(img)
                for img in self.NewImage.imagen_url
            }
            self.actualizarGidBD()
            return ["Producto creado!"]
        except Exception:
            logger.exception("No fue posible crear el producto.")
            raise

    def modificar(self) -> list[str]:
        pass

    def ejecutar(self) -> list[str]:
        """Ejecuta la acción requerida por el evento procesado en la instancia.

        Returns:
            list[str]: Conjunto de resultados obtenidos por las operaciones
            ejecutadas.
        """
        try:
            if self.eventName == "INSERT":
                respuesta = self.crear()
            elif self.cambios.dict(exclude_none=True, exclude_unset=True):
                if self.NewImage.meliID:
                    respuesta = self.modificar()
                else:
                    logger.warning("En el evento no se encontró el GID de "
                                   "Shopify proveniente de la base de datos. "
                                   "Se asume que el producto correspondiente "
                                   "no existe en Shopify. Se creará un "
                                   "producto nuevo con la data actualizada.")
                    respuesta = self.crear()
            else:
                logger.info("Los cambios encontrados no ameritan "
                            "actualizaciones en Shopify.")
                respuesta = ["No se realizaron acciones."]
            return respuesta
        except Exception:
            logger.exception("Ocurrió un problema ejecutando la acción sobre "
                             "el producto.")
            raise
