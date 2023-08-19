
class MeliApiError(Exception):
    def __init__(self, status_code: int,
                 error_message: str | Exception | list[str]):
        self.status_code = int(status_code)
        self.error_message = (str(error_message)
                              if isinstance(error_message, Exception)
                              else error_message)

    def __str__(self):
        return f"Error {self.status_code}: {self.error_message}"


class MeliValidationError(MeliApiError):
    def __init__(self, error_message):
        super().__init__(400, error_message)


class MeliRequestError(MeliApiError):
    pass
