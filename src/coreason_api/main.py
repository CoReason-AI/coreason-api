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

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from coreason_api.config import get_settings
from coreason_api.middleware import TraceIDMiddleware
from coreason_api.routers import architect, runtime, system
from coreason_api.utils.logger import logger


# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up CoReason API...")
    # Initialize DB connection or similar if needed
    yield
    logger.info("Shutting down CoReason API...")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Middleware
    app.add_middleware(TraceIDMiddleware)

    # Global Exception Handler (Hide 500 errors)
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Global exception: {exc}")
        # We can expose details in dev, but PRD says "hide 500 errors".
        # We'll return a generic message.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal Server Error"},
        )

    # Routers
    app.include_router(system.router)
    app.include_router(runtime.router)
    app.include_router(architect.router)

    return app


app = create_app()


def hello_world() -> str:
    logger.info("Hello World!")
    return "Hello World!"
