import contextlib
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from coreason_api.config import get_settings
from coreason_api.middleware import TraceIDMiddleware
from coreason_api.routers import architect, runtime, system
from coreason_api.utils.logger import logger


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup:
    logger.info("Starting Coreason API...")
    # Validate settings or warm up connections could go here.
    get_settings()

    yield

    # Shutdown:
    logger.info("Shutting down Coreason API...")
    # Close connections if any exposed.
    # Adapters mostly manage their own lifecycle or are per-request/stateless.


app = FastAPI(
    title="Coreason API", description="Orchestration layer for CoReason Platform", version="0.1.0", lifespan=lifespan
)

# Middleware
app.add_middleware(TraceIDMiddleware)

# Routers
app.include_router(system.router)
app.include_router(runtime.router)
app.include_router(architect.router)


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the full error with trace ID (already in context via middleware)
    logger.error(f"Unhandled exception: {exc}")

    # Hide details from client
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error. Please contact support."},
    )
