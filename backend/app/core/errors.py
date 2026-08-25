"""Consistent API error shape: ``{"error": {"code": ..., "message": ...}}``."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def not_found(message: str) -> APIError:
    return APIError(status.HTTP_404_NOT_FOUND, "not_found", message)


def rate_limited(message: str = "Rate limit exceeded") -> APIError:
    return APIError(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited", message)


def unauthorized(message: str = "Invalid or missing API key") -> APIError:
    return APIError(status.HTTP_401_UNAUTHORIZED, "unauthorized", message)


def service_unavailable(message: str) -> APIError:
    return APIError(status.HTTP_503_SERVICE_UNAVAILABLE, "service_unavailable", message)


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


_HTTP_CODES = {404: "not_found", 405: "method_not_allowed", 401: "unauthorized"}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(422, "validation_error", "Invalid request parameters")

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        return _error(exc.status_code, code, message)
