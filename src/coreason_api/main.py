# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from coreason_api.config import get_settings
from coreason_api.middleware import TraceIDMiddleware
from coreason_api.routers import architect, runtime, system
from coreason_api.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Load settings/vault on startup
    settings = get_settings()
    logger.info(f"Starting Coreason API (Env: {settings.APP_ENV})")
    yield
    logger.info("Shutting down Coreason API")


app = FastAPI(
    title="CoReason API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware
app.add_middleware(TraceIDMiddleware)

# Routers
app.include_router(system.router, tags=["System"])
app.include_router(runtime.router, tags=["Runtime"])
app.include_router(architect.router, tags=["Architect"])


# Global Exception Handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled exception: {exc}")
    # Hide internal details
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )
