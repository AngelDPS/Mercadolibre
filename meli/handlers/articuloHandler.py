from meli.libs.dynamodb import guardar_MeliIdArticulo
from logging import getLogger
from meli.models.articulo import (
    MArticulo_input,
    # SaleTerms,
    Attributes,
    # ShippingCost,
    Shipping
)
from meli.models.evento import Marticulo_meli as Marticulo
from meli.conexion import MeLiConexion
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

    attr_from_entry = {
        'GTIN': 'codigo_barra',
        'seller_sku': 'referencia',
        'brand': 'marca'
    }

    def actualizarIdBD(self):
        """Actualiza el ID de MercadoLibre para el articulo usando la
        información guardada en la instancia.
        """
        logger.debug(f"MeLi ID de artículo: {self.NewImage.ID}")
        guardar_MeliIdArticulo(
            PK=self.NewImage.PK,
            SK=self.NewImage.SK,
            ID=self.NewImage.ID
        )

    @staticmethod
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
        def extraer_del_mapa_meli(label):
            registros = ['descripcion', 'categoria', 'ID']
            for reg in registros:
                setattr(
                    getattr(self, label),
                    reg,
                    getattr(evento, label)['meli'].get(reg)
                )

        self.eventName = evento.eventName
        campo_precio = self.obtenerCampoPrecio()
        for label in ['NewImage', 'OldImage']:
            setattr(self, label,
                    Marticulo.parse_obj(getattr(evento, label)))
            getattr(self, label).precio = getattr(evento, label)[campo_precio]
            getattr(self, label).habilitado = Habilitado(
                getattr(self, label).habilitado and
                getattr(evento, label)['meli']['habilitado']
            ).name.lower()
            getattr(self, label).tipo_publicacion = TipoPublicacion[
                getattr(evento, label)['meli'].get("tipo_publicacion", "free").upper()
            ].value
            extraer_del_mapa_meli(label)

        self.cambios = (
            evento.obtenerCambios(self.NewImage, self.OldImage)
        )
        self.cambios.pop("ID", None)
        self.session = MeLiConexion(self.NewImage.codigoCompania,
                                    self.NewImage.codigoTienda)

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

    def _obtenerAtributos(self, usar_cambios: bool = False):
        if usar_cambios:
            atributos = [(id, self.cambios.get(registro))
                         for id, registro in self.attr_from_entry.items()]
        else:
            atributos = [(id, getattr(self.NewImage, registro, None))
                         for id, registro in self.attr_from_entry.items()]
        atributos = [Attributes(id=id, value_name=value)
                     for id, value in atributos if value is not None]
        return atributos or None

    def _crear(self):
        self.NewImage.ID = {'imagenes': {
            img: self._cargarImagen(img)
            for img in self.NewImage.imagen_url
        }}
        articuloInput = MArticulo_input(
            **self.NewImage.dict(by_alias=True,
                                 exclude_none=True),
            available_quantity=(self.NewImage.stock_act
                                - self.NewImage.stock_com),
            sale_terms=None,
            pictures=[
                {'id': imgID}
                for imgID in self.NewImage.ID['imagenes'].values()
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
            f'items/{self.NewImage.ID["articulo"]}/description',
            json={'plain_text': self.NewImage.descripcion or ""}
        )

    def _establecerEstatus(self):
        self.session.put(
            f'items/{self.NewImage.ID["articulo"]}',
            json={'status': self.NewImage.habilitado}
        )

    def crear(self) -> list[str]:
        """Función dedicada a crear un producto en Shopify dada
        la información de un evento de artículo INSERT

        Returns:
            str: Respuesta dada una operación exitosa.
        """
        logger.info("Creando producto a partir de artículo.")
        try:
            self.NewImage.ID |= self._crear()
            self._agregarDescripcion()
            self._establecerEstatus()
            self.actualizarIdBD()
            return ["Producto creado!"]
        except Exception:
            logger.exception("No fue posible crear el producto.")
            raise

    def _modificarDescripcion(self):
        if self.cambios.get("descripcion") is not None:
            r = self.session.put(
                f'items/{self.NewImage.ID["articulo"]}/description',
                json={'plain_text': self.NewImage.descripcion}
            )
            r.raise_for_status()
            return "Descripción modificada."
        else:
            return "Descripción no modificada."

    def _obtenerImagenes(self):
        urls_anexados = list(
            set(self.NewImage.imagen_url) - set(self.OldImage.imagen_url)
        )
        self.NewImage.ID['imagenes'] |= {
            img: self._cargarImagen(img)
            for img in urls_anexados
        }
        if self.cambios.get("imagen_url", None) is not None:
            return [
                {'id': self.NewImage.ID['imagenes'][fname]}
                for fname in self.cambios["imagen_url"]
            ]
        else:
            return None

    def _cambioCantidad(self):
        stock_new = (self.NewImage.stock_act - self.NewImage.stock_com)
        stock_old = (self.OldImage.stock_act - self.OldImage.stock_com)
        if stock_new != stock_old:
            return stock_new
        else:
            return None

    def _modificarArticulo(self):
        articuloInput = MArticulo_input(
            **self.cambios,
            available_quantity=self._cambioCantidad(),
            pictures=self._listaImagenesModificadas(),
            attributes=self._obtenerAtributos(usar_cambios=True)
        ).dict(exclude_none=True, exclude_unset=True)
        logger.debug(articuloInput)
        if articuloInput:
            response = self.session.put(
                f'items/{self.NewImage.ID["articulo"]}',
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
        try:
            if self.eventName == "INSERT":
                respuesta = self.crear()
            elif self.cambios:
                if self.NewImage.ID:
                    respuesta = self.modificar()
                else:
                    logger.warning("En el evento no se encontró el ID de "
                                   "MercadoLibre proveniente de la base de "
                                   "datos. Se asume que el articulo "
                                   "correspondiente no existe en MercadoLibre."
                                   " Se creará un articulo nuevo con la data "
                                   "actualizada.")
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
