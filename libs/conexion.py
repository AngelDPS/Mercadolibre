from libs.dynamodb import (
    obtener_MeliAccessToken,
    guardar_MeliAccessToken,
    obtener_MeliClientCredentials
)
from requests_oauthlib import OAuth2Session
from logging import getLogger
from decimal import Decimal

logger = getLogger("meli.conexion")


class MeLiConexion(OAuth2Session):
    token_url = r"https://api.mercadolibre.com/oauth/token"
    codigoCompania: str
    codigoTienda: str

    def token_updater(self, token: dict):
        for k, v in token.items():
            if isinstance(v, float):
                token[k] = Decimal(v)
        guardar_MeliAccessToken(self. codigoCompania, self.codigoTienda,
                                token)

    def _fetchToken(self):
        authorization_url, state = self.authorization_url(
            'https://auth.mercadolibre.com.ve/authorization'
        )
        print(f'Ve a {authorization_url} y autoriza el acceso.')
        authorization_response = input("Provee el callback URL completo: ")
        self.fetch_token(
            self.token_url,
            authorization_response=authorization_response,
            include_client_id=True,
            client_secret=self.auto_refresh_kwargs['client_secret']
        )
        self.token_updater(self.token)

    def __init__(self, codigoCompania: str, codigoTienda: str, **kwargs):
        self.codigoCompania = codigoCompania
        self.codigoTienda = codigoTienda
        client = obtener_MeliClientCredentials(codigoCompania, codigoTienda)
        super().__init__(client['client_id'],
                         # redirect_uri=config['redirect_uri'],
                         auto_refresh_url=self.token_url,
                         auto_refresh_kwargs=client,
                         token_updater=self.token_updater,
                         **kwargs)
        try:
            self.token = obtener_MeliAccessToken(self.codigoCompania,
                                                 self.codigoTienda)
            logger.debug(f"{self.token = }")
        except KeyError:
            self.warning("No se pudo obtener el refresh token."
                         "Se intentará generar un token nuevo.")
            if not self.redirect_uri:
                raise ValueError("En caso de no haber un token "
                                 "preexistente, se debe suministrar el "
                                 "'redirect_uri' para procurar un nuevo "
                                 "token.")
            self._fetchToken()

    def request(
        self,
        method,
        meLi_resource,
        data=None,
        headers=None,
        withhold_token=False,
        **kwargs
    ):
        meLi_api = 'https://api.mercadolibre.com/'
        url = (meLi_api + meLi_resource
               if meLi_api not in meLi_resource else meLi_resource)
        response = super().request(method,
                                   url,
                                   data,
                                   headers,
                                   withhold_token,
                                   **kwargs)
        logger.info(f"{method} realizado a '{response.url}'")
        logger.debug(f'Retornó un status {response.status_code}'
                     f'\t{response.reason}\nContenido:\n{response.text}'
                     f'\nHeaders:\n{response.headers}')
        return response
