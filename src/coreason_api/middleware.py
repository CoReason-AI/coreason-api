import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from coreason_api.utils.logger import logger


class TraceIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())

        # Attach to request state for use in endpoints
        request.state.trace_id = trace_id

        # Log context (using loguru context binding if we wanted, but for now simple logging)
        # Ideally we'd bind it to loguru context so all logs have it.
        # with logger.contextualize(trace_id=trace_id):
        #    response = await call_next(request)

        # The PRD says: "Tracing: Assign a UUID Trace ID (via Middleware)."
        # It doesn't explicitly mandate log context binding, but it's good practice.

        with logger.contextualize(trace_id=trace_id):
            response = await call_next(request)

        response.headers["X-Trace-ID"] = trace_id
        return response
