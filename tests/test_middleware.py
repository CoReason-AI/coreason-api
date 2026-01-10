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
from unittest.mock import MagicMock, patch

import pytest
from coreason_api.middleware import TraceIDMiddleware
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware import Middleware


@pytest.fixture  # type: ignore[misc]
def app() -> FastAPI:
    app = FastAPI(middleware=[Middleware(TraceIDMiddleware)])

    @app.get("/test")
    async def test_endpoint(request: Request) -> dict[str, str]:
        return {"status": "ok"}

    return app


@pytest.fixture  # type: ignore[misc]
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_trace_id_generated_if_missing(client: TestClient) -> None:
    response = client.get("/test")
    assert response.status_code == 200
    assert "X-Trace-ID" in response.headers
    trace_id = response.headers["X-Trace-ID"]
    try:
        uuid.UUID(trace_id)
    except ValueError:
        pytest.fail("X-Trace-ID is not a valid UUID")


def test_trace_id_preserved_if_present(client: TestClient) -> None:
    custom_trace_id = "123e4567-e89b-12d3-a456-426614174000"
    response = client.get("/test", headers={"X-Trace-ID": custom_trace_id})
    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == custom_trace_id


def test_logger_context(client: TestClient) -> None:
    # Patch the logger in middleware.py
    with patch("coreason_api.middleware.logger") as mock_logger:
        # Mock contextualize to return a context manager
        context_manager = MagicMock()
        mock_logger.contextualize.return_value = context_manager
        context_manager.__enter__.return_value = None
        context_manager.__exit__.return_value = None

        client.get("/test")

        # Verify contextualize was called with a trace_id
        mock_logger.contextualize.assert_called_once()
        args, kwargs = mock_logger.contextualize.call_args
        assert "trace_id" in kwargs


# --- Edge Cases ---


def test_trace_id_custom_format(client: TestClient) -> None:
    # Verify that non-standard Trace IDs are accepted and preserved
    # This ensures flexibility for integrating with external systems that might not use standard UUIDs
    custom_id = "request-12345"
    response = client.get("/test", headers={"X-Trace-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == custom_id
