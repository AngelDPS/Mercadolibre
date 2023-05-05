from handlers.conexion import MeLiConexion
from libs.custom_log import getLogger
import re

logger = getLogger(__name__)


class Articulo:
    def __init__(self, codigoCompania: str):
        self.session = MeLiConexion(codigoCompania)

    def añadirImagen(self, id, imagePath):
        pattern = r"(?P<fname>\w*\.(?P<ftype>jpg|jpeg|png|gif|webp))$"
        match = re.search(pattern, imagePath)
        if not match:
            raise ValueError("El tipo de archivo usado no tiene soporte. "
                             "Tipos de archivo válidos son "
                             "[jpg, jpeg, png, gif, webp].")
        mime_type = ("image/jpeg" if match['ftype'] == "jpg"
                     else f"image/{match['ftype']}")
        with open(imagePath, 'rb') as imageFile:
            files = {'file': (match["fname"], imageFile, mime_type)}
            r = self.session.post('pictures/items/upload', files=files)
        logger.debug(r.text)
        self.session.post(f'items/{id}/pictures', json={'id': r.json()['id']})
        return r

    def crear(self, payload, descripcion):
        r = self.session.post('items', json=payload)
        self.session.post(f'items/{r.json()["id"]}/description',
                          json={'plain_text': descripcion})

    def modificar(self, id, payload, descripcion=None):
        self.session.put(f'items/{id}', json=payload)
        if descripcion:
            self.session.post(f'items/{id}/description',
                              json={'plain_text': descripcion})

    def pausar(self, id):
        payload = {
            "status": "paused"
        }
        self.modificar(id, payload)

    def reanudar(self, id):
        payload = {
            "status": "active"
        }
        self.modificar(id, payload)

    def predecirCategoria(self, nombre):
        self.session.get('sites/MLV/domain_discovery/search',
                         params={'q': nombre})

    def añadirImagenes(self, id, images):
        pass


descripcion = "Descripción de ítem de prueba\ncon dos líneas."

payload = {
    "title": "Item de test - No Ofertar",
    "condition": "new",
    "category_id": "MLV3530",
    "price": 30,
    "currency_id": "USD",
    "listing_type_id": "free",
    "available_quantity": 1,
    "buying_mode": "buy_it_now",
    "sale_terms": [
        {
            "id": "WARRANTY_TYPE",
            "value_name": "Garantía del vendedor"
        },
        {
            "id": "WARRANTY_TIME",
            "value_name": "90 días"
        }
    ],
    "pictures": [
        {
            "source": "http://mla-s2-p.mlstatic.com/968521-MLA20805195516_072016-O.jpg"
        }
    ],
    "attributes": [
        {
            "id": "BRAND",
            "value_name": "Marca del producto"
        },
        {
            "id": "MODEL",
            "value_name": "Modelo del producto"
        },
        {
            "id": "SELLER_SKU",
            "value_name": "7898095297749"
        }
    ],
    "shipping": {
        "mode": "custom",
                "local_pick_up": True,
                "free_shipping": False,
                "methods": [],
                "costs": [
                    {
                        "description": "TEST1",
                        "cost": "70"
                    },
                    {
                        "description": "TEST2 ",
                        "cost": "80"
                    }
                ]
    }
}

if __name__ == "__main__":
    art = Articulo('ADPS')
    art.pausar("MLV749503490")
