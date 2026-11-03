"""Erros de negócio convertidos automaticamente em respostas JSON {"error": ...}."""


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


class NotFound(ApiError):
    def __init__(self, message):
        super().__init__(message, 404)

