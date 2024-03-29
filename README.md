Desarrollo para la integración de Mercadolibre con sistemas de bases de datos.

## Datos para guardar en DynamoDB por tienda

Al registro de tienda para MercadoLibre en DynamoDB se le debe agregar la siguiente data (en un mapa) manualmente, después de obtenerla de MercadoLibre via web:

    "meli": {
    "client": {
    "client_id": "2416149642134557",
    "client_secret": "p21OoANgIO25F6OZtGFZZ5WQQqc3SDWE"
    },
    "refresh_token": {
    "access_token": "APP_USR-2416149642134557-072614-175533b370f242291f8058b2513a1c8d-95798694",
    "expires_at": "",
    "expires_in": -10, # SE DEBE PONER MANUALMENTE EN UN VALOR NEGATIVO
    "refresh_token": "TG-64c16b2997a65600015c3014-95798694",
    "scope": [
        "offline_access",
        "read",
        "write"
    ],
    "token_type": "Bearer",
    "user_id": "95798694"
    }
    }

## Variables de parameter

* `MELI_PRECIO`: Establece que campo de precio a usar de la base de datos, con formato `prec_vta[num]`
* `SQSURL`: Url con la cola de SQS para eventos no-procesados.

## Obtener el `ACCESS_TOKEN`

[MercadoLibre](https://developers.mercadolibre.com.ve/es_ar/autenticacion-y-autorizacion "Documentanción para la autenticación y autorización para el acceso a la API de MercadoLibre.") usa el protocolo OAuth 2.0 para conceder autorización a los recursos de la API acorde al usuario.

El flujo de trabajo que emplea es el de [*Authorization Code Grant (Web Application Flow)*](https://requests-oauthlib.readthedocs.io/en/latest/oauth2_workflow.html#web-application-flow "Documentación del paquete Requests-Oauthlib usada para obtener un token de acceso.").

Para obtener un token de acceso por primera vez, se genera un url a través del cual el usuario debe confirmar la integración de su cuenta con la API de administración. Confirmada la autorización, se redirecciona al usuario a una URI predefinida en la API de administración (callback URI), para otorgarle un código canjeable por el token de acceso.

El callback URL completo se le otorga al programa para canjearlo por un token que se guarda en la base de datos.

Posterior a esto el proceso de refrescamiento ocurre automáticamente, manteniendo la base de datos actualizada.

## Crear usuario de pruebas

Para crear un usuario de pruebas se manda el siguiente request al recurso `users/test_user` de la API de Mercadolibre, donde el `ACCESS_TOKEN` es 

    curl -X POST -H 'Authorization: Bearer $ACCESS_TOKEN' -H "Content-type: application/json" -d
    '{
        "site_id":"MLA"
    }'
    'https://api.mercadolibre.com/users/test_user'


Verificar:
1) Al publicarse el producto en meli, eliminar los errores

Validaciones:
1) Stock = 1
2) Precio > 2



