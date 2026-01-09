import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from coreason_api.utils.logger import logger


class TraceIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every request has a Trace ID.
    - Reads X-Trace-ID from headers.
    - Generates one if missing.
    - Adds it to response headers.
    - Contextualizes the logger.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        trace_id = request.headers.get("X-Trace-ID")
        if not trace_id:
            trace_id = str(uuid.uuid4())

        # Bind trace_id to logger context
        with logger.contextualize(trace_id=trace_id):
            response = await call_next(request)

        response.headers["X-Trace-ID"] = trace_id
        return response
