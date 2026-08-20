from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        field: str | None = None,
        retryable: bool = False,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field = field
        self.retryable = retryable


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    content: dict[str, Any] = {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "field": exc.field,
            "retryable": exc.retryable,
            "request_id": request_id,
        }
    }
    return JSONResponse(status_code=exc.status_code, content=content)
