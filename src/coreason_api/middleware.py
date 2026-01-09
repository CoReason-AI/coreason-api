# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from coreason_api.utils.logger import logger


class TraceIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that assigns a UUID Trace ID to every request.
    It looks for 'X-Trace-ID' in the request headers; if missing, it generates one.
    The Trace ID is bound to the logger context and added to the response headers.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())

        # Bind trace_id to the logger for the duration of this request
        with logger.contextualize(trace_id=trace_id):
            logger.debug(f"Starting request with Trace ID: {trace_id}")
            response = await call_next(request)
            response.headers["X-Trace-ID"] = trace_id
            logger.debug(f"Finished request with Trace ID: {trace_id}")
            return response
