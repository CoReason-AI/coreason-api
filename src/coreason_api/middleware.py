import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class TraceIDMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = request.headers.get("X-Trace-ID")
        if not trace_id:
            trace_id = str(uuid.uuid4())

        # We might want to set this in a ContextVar for logging, but
        # loguru or the Auditor might handle that.
        # For now, we ensure it's passed downstream and returned in response.

        # Inject into request scope so endpoints can access it easily if needed
        request.state.trace_id = trace_id

        response = await call_next(request)

        # Ensure header is present in response
        response.headers["X-Trace-ID"] = trace_id

        return response
