from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Union, Dict, Any
import logging
from prometheus_client import Counter

logger = logging.getLogger(__name__)

# Metrics
error_counter = Counter('error_total', 'Total errors', ['type'])

class CustomHTTPException(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str = None,
        error_type: str = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code
        self.error_type = error_type

async def http_exception_handler(
    request: Request,
    exc: Union[HTTPException, CustomHTTPException]
) -> JSONResponse:
    """HTTP istisnaları için özel işleyici"""
    error_data: Dict[str, Any] = {"detail": exc.detail}
    
    if isinstance(exc, CustomHTTPException):
        if exc.error_code:
            error_data["error_code"] = exc.error_code
        if exc.error_type:
            error_data["error_type"] = exc.error_type
            error_counter.labels(type=exc.error_type).inc()
    else:
        error_counter.labels(type="http_error").inc()

    logger.error(
        f"HTTP {exc.status_code} error occurred",
        extra={
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host,
            "error_data": error_data
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_data
    )

async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Doğrulama hataları için özel işleyici"""
    error_counter.labels(type="validation_error").inc()
    
    logger.error(
        "Validation error occurred",
        extra={
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host,
            "error_detail": str(exc)
        }
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": str(exc)
        }
    )

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Genel hatalar için özel işleyici"""
    error_counter.labels(type="general_error").inc()
    
    logger.error(
        f"Unexpected error occurred: {str(exc)}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host,
            "error_type": type(exc).__name__
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_type": type(exc).__name__
        }
    )

class ErrorMessages:
    """Hata mesajları için sabitler"""
    INVALID_TOKEN = "Invalid or expired token"
    RATE_LIMIT_EXCEEDED = "Rate limit exceeded"
    INVALID_IP = "IP address not allowed"
    CONNECTION_ERROR = "Connection error occurred"
    VALIDATION_ERROR = "Validation error occurred"
    INTERNAL_ERROR = "Internal server error"
