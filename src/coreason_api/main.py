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

from fastapi import FastAPI

from coreason_api.middleware import TraceIDMiddleware
from coreason_api.routers import architect, runtime, system
from coreason_api.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan events for the application.
    """
    logger.info("Starting Coreason API...")
    yield
    logger.info("Shutting down Coreason API...")


def create_app() -> FastAPI:
    """
    Factory function to create the FastAPI application.
    """
    app = FastAPI(
        title="CoReason API",
        description="Orchestration Layer for CoReason Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add Middleware
    app.add_middleware(TraceIDMiddleware)

    # Include Routers
    app.include_router(system.router)
    app.include_router(runtime.router)
    app.include_router(architect.router)

    return app


app = create_app()


def hello_world() -> str:
    logger.info("Hello World!")
    return "Hello World!"
