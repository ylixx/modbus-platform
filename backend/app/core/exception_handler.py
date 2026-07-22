"""Global exception handlers — unified error response + logging."""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger
import traceback


def register_exception_handlers(app: FastAPI):
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": exc.detail,
                "data": None,
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        logger.warning(f"ValueError: {exc} | {request.url.path}")
        return JSONResponse(
            status_code=400,
            content={
                "code": 400,
                "message": str(exc),
                "data": None,
            },
        )

    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError):
        logger.warning(f"PermissionError: {exc} | {request.url.path}")
        return JSONResponse(
            status_code=403,
            content={
                "code": 403,
                "message": "权限不足",
                "data": None,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        # Log full traceback
        tb = traceback.format_exc()
        logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}\n{tb}\nURL: {request.method} {request.url.path}")

        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "message": "服务器内部错误，请稍后重试",
                "data": None,
            },
        )
