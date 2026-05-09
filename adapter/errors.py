import os
from typing import Any, Callable, Optional

from fastapi import FastAPI, Request
from fastapi import HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.models.errors import (
    CommitTimeValidationFailure,
    ConcurrencyConflictError,
    DirectoryStructureCorruptedError,
    ExternalServiceError,
    NotFound,
    PLMError,
    PreconditionFailure,
    SessionClosedError,
    StructuralInconsistencyError,
)


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return str(value) if value else None


def _err(
    *,
    code: str,
    message: str,
    details: Optional[Any] = None,
    status_code: int = 400,
    request_id: str | None = None,
    headers: Optional[dict[str, str]] = None,
) -> JSONResponse:
    payload: dict[str, Any] = {"ok": False, "error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    response_headers = dict(headers or {})
    if request_id:
        response_headers["X-Request-ID"] = request_id
    return JSONResponse(status_code=status_code, content=payload, headers=response_headers or None)


def _expose_internal_error_details() -> bool:
    return (os.getenv("PLM_DEBUG_ERRORS") or "").strip().lower() in {"1", "true", "yes", "on"}


def _http_error_code(status_code: int) -> str:
    return {
        400: "INVALID_INPUT",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        416: "RANGE_NOT_SATISFIABLE",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }.get(int(status_code), "HTTP_ERROR")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(FastAPIHTTPException)
    async def _handle_fastapi_http_error(request: Request, exc: FastAPIHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else None
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        code = _http_error_code(int(exc.status_code))
        return _err(
            code=code,
            message=str(message),
            details=detail,
            status_code=int(exc.status_code),
            request_id=_request_id(request),
            headers=dict(exc.headers or {}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_starlette_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else None
        message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        code = _http_error_code(int(exc.status_code))
        return _err(
            code=code,
            message=str(message),
            details=detail,
            status_code=int(exc.status_code),
            request_id=_request_id(request),
            headers=dict(exc.headers or {}),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _err(
            code="INVALID_INPUT",
            message="Request validation failed",
            details=exc.errors(),
            status_code=400,
            request_id=_request_id(request),
        )

    def _plm_handler(code: str, *, status_code: int = 400) -> Callable[[Request, Exception], JSONResponse]:
        async def _handle(request: Request, exc: Exception) -> JSONResponse:
            return _err(code=code, message=str(exc), status_code=status_code, request_id=_request_id(request))

        return _handle

    app.add_exception_handler(NotFound, _plm_handler("NOT_FOUND"))
    app.add_exception_handler(PreconditionFailure, _plm_handler("PRECONDITION"))
    app.add_exception_handler(ExternalServiceError, _plm_handler("EXTERNAL_SERVICE", status_code=502))
    app.add_exception_handler(ConcurrencyConflictError, _plm_handler("CONCURRENCY"))
    app.add_exception_handler(CommitTimeValidationFailure, _plm_handler("COMMIT_VALIDATION"))
    app.add_exception_handler(StructuralInconsistencyError, _plm_handler("STRUCTURAL_INCONSISTENCY"))
    app.add_exception_handler(SessionClosedError, _plm_handler("SESSION_CLOSED"))
    app.add_exception_handler(DirectoryStructureCorruptedError, _plm_handler("DIRECTORY_STRUCTURE_CORRUPTED"))

    @app.exception_handler(PLMError)
    async def _handle_plm_fallback(request: Request, exc: PLMError) -> JSONResponse:
        return _err(code="PLM_ERROR", message=str(exc), status_code=400, request_id=_request_id(request))

    @app.exception_handler(Exception)
    async def _handle_unknown(request: Request, exc: Exception) -> JSONResponse:
        details = str(exc) if _expose_internal_error_details() else None
        return _err(code="UNKNOWN", message="Internal server error", details=details, status_code=500, request_id=_request_id(request))
