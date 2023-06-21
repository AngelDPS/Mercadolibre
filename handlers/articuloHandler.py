from libs.dynamodb import guardar_MeliIdArticulo
from logging import getLogger
from models.articulo import (
    MArticulo_input,
    # SaleTerms,
    Attributes,
    # ShippingCost,
    Shipping
)
from models.evento import Marticulo_meli as Marticulo
from libs.conexion import MeLiConexion
from os import environ
from re import search
import requests
import boto3
from enum import Enum

logger = getLogger(__name__)
s3_client = boto3.client('s3', region_name=environ.get("AWS_REGION"),
                         config=boto3.session.Config(signature_version='s3v4'))


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


class ArticuloHandler:

    def obtenerCampoPrecio() -> str:
        """Lee el campo de precio a usar para el artículo.

        Returns:
            str: Campo de precio a usar.
        """
        try:
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
        def extraer_del_mapa_meli(d: dict):
            registros = ['descripcion', 'categoria', 'ID']
            r = {}
            if d.get('meli'):
                for reg in registros:
                    if reg in d['meli']:
                        r[reg] = d['meli'][reg]
            return r

        if not (evento.OldImage.get('meli', {}).get('habilitado') or
                evento.cambios.get('meli', {}).get('habilitado')):
            logger.info(
                """El articulo no está habilitado para MercadoLibre y será
                ignorado.
                Para cambiar esto, establezca el registro meli.habilitado
                con el valor '1'."""
            )
            self.procesar = False
        else:
            self.procesar = True

            campo_precio = environ.get('MELI_PRECIO')

            self.cambios = evento.cambios
            self.cambios.get('meli', {}).pop('ID', None)
            if campo_precio in self.cambios:
                self.cambios['precio'] = self.cambios[campo_precio]
            if ('habilitado' in self.cambios
                    or 'habilitado' in self.cambios.get('meli', {})):
                self.cambios['habilitado'] = Habilitado(
                    self.cambios.get('habilitado',
                                     evento.OldImage.get('habilitado')) and
                    self.cambios.get('meli', {}).get(
                        'habilitado',
                        evento.OldImage.get('meli', {}).get('habilitado')
                    )
                ).name.lower()
            if 'tipo_publicacion' in self.cambios.get('meli', {}):
                self.cambios['tipo_publicacion'] = TipoPublicacion[
                    self.cambios['meli']['tipo_publicacion'].upper()
                ].value
            self.cambios |= extraer_del_mapa_meli(self.cambios)
            self.cambios = Marticulo.parse_obj(self.cambios)

            self.OldImage = evento.OldImage
            if self.OldImage:
                self.OldImage['precio'] = self.OldImage[campo_precio]
                self.OldImage['habilitado'] = Habilitado(
                    self.OldImage.get('habilitado') and
                    self.OldImage.get('meli', {}).get('habilitado')
                ).name.lower()
                self.OldImage['tipo_publicacion'] = TipoPublicacion[
                    self.OldImage.get('meli', {}).get("tipo_publicacion",
                                                      "free").upper()
                ].value
                self.OldImage |= extraer_del_mapa_meli(self.OldImage)
            self.OldImage = Marticulo.parse_obj(self.OldImage)

            self.session = MeLiConexion(
                self.OldImage.codigoCompania or self.cambios.codigoCompania,
                self.OldImage.codigoTienda or self.cambios.codigoTienda
            )

    def actualizarIdBD(self):
        """Actualiza el ID de MercadoLibre para el articulo usando la
        información guardada en la instancia.
        """
        logger.debug(f"MeLi ID de artículo: {self.OldImage.ID}")
        guardar_MeliIdArticulo(
            PK=self.OldImage.PK or self.cambios.PK,
            SK=self.OldImage.SK or self.cambios.SK,
            ID=self.OldImage.ID
        )

    @staticmethod
    def _procesarImagen(fname: str):
        pattern = r"\.(jpg|jpeg|png|gif|webp)$"
        try:
            fextension = search(pattern, fname)[1]
        except IndexError or TypeError:
            raise ValueError("El tipo de archivo usado no tiene soporte. "
                             "Tipos de archivo válidos son "
                             "[jpg, jpeg, png, gif, webp].")
        mime_type = ("image/jpeg" if fextension == "jpg"
                     else f"image/{fextension}")
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': environ.get("BUCKET_NAME"),
                    'Key': f"imagenes/{fname}"},
            ExpiresIn=3600
        )
        imagen = requests.get(url).content
        return {'file': (fname, imagen, mime_type)}

    def _cargarImagen(self, file):
        try:
            files = self._procesarImagen(file)
            r = self.session.post('pictures/items/upload', files=files)
            imgId = r.json()['id']
            return imgId
        except ValueError as err:
            logger.exception(err)
            logger.warning(f"El tipo de imagen de '{file}' no tiene soporte en"
                           " MeLi y se saltará su carga.")
            return None
        except Exception as err:
            logger.exception(err)
            logger.warning(f"No se pudo asociar '{file}' al artículo.")
            try:
                return imgId
            except NameError:
                logger.warning("Hubo problemas cargando la imagen a "
                               "MercadoLibre.")
                return None

    def _obtenerAtributos(self):
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
        articuloInput = MArticulo_input(
            **self.cambios.dict(by_alias=True,
                                exclude_none=True),
            available_quantity=(self.cambios.stock_act
                                - self.cambios.stock_com),
            sale_terms=None,
            pictures=[
                {'id': imgID}
                for imgID in self.OldImage.ID['imagenes'].values()
            ],
            attributes=self._obtenerAtributos(),
            shipping=Shipping()
        ).dict(exclude_none=True)
        logger.debug(articuloInput)
        response = self.session.post(
            'items',
            json=articuloInput
        )
        id_dict = {
            'articulo': response.json()['id']
        }
        return id_dict

    def _agregarDescripcion(self):
        self.session.post(
            f'items/{self.OldImage.ID["articulo"]}/description',
            json={'plain_text': self.cambios.descripcion or "Sin descripción."}
        )

    def _establecerEstatus(self):
        self.session.put(
            f'items/{self.OldImage.ID["articulo"]}',
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
            self.OldImage.ID |= {'imagenes': {
                img: self._cargarImagen(img)
                for img in self.cambios.imagen_url
            }}
            self.OldImage.ID |= self._crear()
            self._agregarDescripcion()
            self._establecerEstatus()
            self.actualizarIdBD()
            return ["Producto creado!"]
        except Exception:
            logger.exception("No fue posible crear el producto.")
            raise

    def _modificarDescripcion(self):
        if "descripcion" in self.cambios.dict(exclude_unset=True):
            r = self.session.put(
                f'items/{self.OldImage.ID["articulo"]}/description',
                json={'plain_text': self.cambios.descripcion
                      or "Sin descripción."}
            )
            r.raise_for_status()
            return "Descripción modificada."
        else:
            return "Descripción no modificada."

    def _obtenerImagenes(self):
        urls_anexados = list(
            set(self.cambios.imagen_url) - set(self.OldImage.imagen_url)
        )
        self.OldImage.ID['imagenes'] |= {
            img: self._cargarImagen(img)
            for img in urls_anexados
        }
        if "imagen_url" in self.cambios.dict(exclude_unset=True):
            return [
                {'id': self.OldImage.ID['imagenes'][fname]}
                for fname in self.cambios.imagen_url
            ]
        else:
            return None

    def _cambioCantidad(self):
        stock_new = (self.cambios.stock_act or self.OldImage.stock_act
                     - self.cambios.stock_com or self.OldImage.stock_com)
        stock_old = (self.OldImage.stock_act - self.OldImage.stock_com)
        if stock_new != stock_old:
            return stock_new
        else:
            return None

    def _modificarArticulo(self):
        articuloInput = MArticulo_input(
            **self.cambios.dict(exclude_unset=True),
            available_quantity=self._cambioCantidad(),
            pictures=self._obtenerImagenes(),
            attributes=self._obtenerAtributos()
        ).dict(exclude_none=True, exclude_unset=True)
        logger.debug(articuloInput)
        if articuloInput:
            response = self.session.put(
                f'items/{self.OldImage.ID["articulo"]}',
                json=articuloInput
            )
            response.raise_for_status()
            return "Producto Modificado"
        else:
            return "Producto no modificado."

    def modificar(self) -> list[str]:
        try:
            respuestas = []
            respuestas.append(self._modificarDescripcion())
            respuestas.append(self._modificarArticulo())
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
            try:
                if self.cambios.dict(exclude_unset=True):
                    logger.info("Se aplicarán los cambios en MercadoLibre.")
                    if not self.OldImage.ID:
                        logger.info(
                            "En el evento no se encontró el ID de "
                            "MercadoLibre proveniente de la base de "
                            "datos. Se asume que el articulo "
                            "correspondiente no existe en MercadoLibre."
                            " Se creará un articulo nuevo con la data "
                            "actualizada."
                        )
                        self.cambios = Marticulo.parse_obj(
                            self.OldImage.dict()
                            | self.cambios.dict(exclude_unset=True)
                        )
                        respuesta = self.crear()
                    else:
                        respuesta = self.modificar()
                else:
                    logger.info("Los cambios encontrados no ameritan "
                                "actualizaciones en MercadoLibre.")
                    respuesta = ["No se realizaron acciones."]
            except Exception:
                logger.exception("Ocurrió un problema ejecutando la acción "
                                 "sobre el producto.")
                raise
        else:
            logger.info("El artículo no está habilitado para procesarse en "
                        "MercadoLibre.")
            respuesta = ["Artículo inhabilitado."]

        return respuesta
