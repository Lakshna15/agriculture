import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.middleware.security_headers import SECURITY_HEADERS

logger = logging.getLogger(__name__)

# What a validation error tells the client: where the problem is, what kind it
# is and a readable message. FastAPI's default also includes "input", the
# submitted value itself, which would send a rejected password straight back
# in the response and repeat any oversized field in full.
_VALIDATION_ERROR_FIELDS = ("type", "loc", "msg")


async def _validation_error_response(_request: Request, error: RequestValidationError) -> JSONResponse:
    details = [
        {field: issue[field] for field in _VALIDATION_ERROR_FIELDS if field in issue}
        for issue in error.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(details)},
    )


async def _unexpected_error_response(request: Request, _error: Exception) -> JSONResponse:
    # The details go to the server log only. The client gets the same JSON
    # shape as every other error, with nothing about the cause.
    logger.exception("Unhandled error while serving %s %s", request.method, request.url.path)
    # Starlette sends this response from its outermost layer, outside every
    # added middleware, so the security headers have to be attached here.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
        headers=SECURITY_HEADERS,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error_response)
    app.add_exception_handler(Exception, _unexpected_error_response)
