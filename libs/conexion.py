from libs.dynamodb import (
    obtener_meli_access_token,
    guardar_meli_access_token,
    obtener_meli_client_credentials,
    guardar_meli_error
)
from libs.exceptions import MeliRequestError, MeliValidationError
from requests_oauthlib import OAuth2Session
from requests.exceptions import HTTPError
from decimal import Decimal
from aws_lambda_powertools import Logger

logger = Logger(child=True)


class MeliConexion(OAuth2Session):
    token_url = r"https://api.mercadolibre.com/oauth/token"
    CODIGO_COMPANIA: str
    CODIGO_TIENDA: str

    def token_updater(self, token: dict):
        for k, v in token.items():
            if isinstance(v, float):
                token[k] = Decimal(v)
        guardar_meli_access_token(self.CODIGO_COMPANIA, self.CODIGO_TIENDA,
                                  token)

    def _fetch_token(self):
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

    def __init__(self, codigo_compania: str, codigo_tienda: str, **kwargs):
        self.CODIGO_COMPANIA = codigo_compania
        self.CODIGO_TIENDA = codigo_tienda
        client = obtener_meli_client_credentials(codigo_compania,
                                                 codigo_tienda)
        super().__init__(client['client_id'],
                         # redirect_uri=config['redirect_uri'],
                         auto_refresh_url=self.token_url,
                         auto_refresh_kwargs=client,
                         token_updater=self.token_updater,
                         **kwargs)
        try:
            self.token = obtener_meli_access_token(self.CODIGO_COMPANIA,
                                                   self.CODIGO_TIENDA)
            logger.debug(f"{self.token = }")
        except KeyError:
            self.warning("No se pudo obtener el refresh token."
                         "Se intentará generar un token nuevo.")
            if not self.redirect_uri:
                raise ValueError("En caso de no haber un token "
                                 "preexistente, se debe suministrar el "
                                 "'redirect_uri' para procurar un nuevo "
                                 "token.")
            self._fetch_token()

    def request(
        self,
        method: str,
        meli_resource: str,
        data: dict = None,
        headers: dict = None,
        withhold_token: bool = False,
        PK: str = "",
        SK: str = "",
        **kwargs
    ):
        meli_api = 'https://api.mercadolibre.com/'
        url = (meli_api + meli_resource
               if meli_api not in meli_resource else meli_resource)
        try:
            response = super().request(method,
                                       url,
                                       data,
                                       headers,
                                       withhold_token,
                                       **kwargs)
        except Exception as err:
            logger.exception("Ocurrión un error al realizar la petición")
            raise MeliRequestError(600, err)
        logger.info(f"{method} realizado a '{response.url}'")
        logger.debug(f'Retornó un status {response.status_code}'
                     f'\t{response.reason}\nContenido:\n{response.text}'
                     f'\nHeaders:\n{response.headers}')
        try:
            response.raise_for_status()
        except HTTPError as err:
            if response.status_code > 400:
                logger.error(
                    "Ocurrió un error con el servidor de MercadoLibre")
                raise MeliRequestError(response.status_code, err)
            elif response.status_code == 400:
                if response.json().get("error") == "validation_error":
                    error_msg = [cause.get("message")
                                 for cause in response.json().get("cause", {})
                                 if cause.get("type") == "error"]
                    logger.error(error_msg)
                    if PK and SK:
                        guardar_meli_error(PK, SK, error_msg)
                    raise MeliValidationError(error_msg)
        return response
