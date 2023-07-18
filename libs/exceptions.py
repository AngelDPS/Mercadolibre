
class MeliApiError(Exception):
    def __init__(self, status_code, error_message):
        self.status_code = status_code
        self.error_message = error_message

    def __str__(self):
        return f"Error {self.status_code}: {self.error_message}"


class MeliValidationError(MeliApiError):
    def __init__(self, error_message):
        super().__init__(400, error_message)


class MeliRequestError(MeliApiError):
    pass
