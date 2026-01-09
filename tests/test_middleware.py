# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from coreason_api.middleware import TraceIDMiddleware
from coreason_api.utils.logger import logger


@pytest.fixture  # type: ignore[misc]
def app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)

    @app.get("/")  # type: ignore[misc]
    async def root() -> dict[str, str]:
        logger.info("Inside handler")
        return {"message": "ok"}

    return app


@pytest.fixture  # type: ignore[misc]
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


def test_trace_id_generation(client: TestClient) -> None:
    """Test that a Trace ID is generated if missing."""
    response = client.get("/")
    assert response.status_code == 200
    assert "X-Trace-ID" in response.headers
    assert len(response.headers["X-Trace-ID"]) > 0


def test_trace_id_propagation(client: TestClient) -> None:
    """Test that an existing Trace ID is preserved."""
    custom_trace_id = "test-trace-id-123"
    response = client.get("/", headers={"X-Trace-ID": custom_trace_id})
    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == custom_trace_id


def test_trace_id_logging(client: TestClient) -> None:
    """Test that the Trace ID is bound to the logger context."""
    log_sink = []

    def sink(message: str) -> None:
        # In Loguru, the message object has a .record attribute
        record = message.record  # type: ignore[attr-defined]
        log_sink.append(record)

    handler_id = logger.add(sink, level="DEBUG")

    try:
        response = client.get("/")
        assert response.status_code == 200
        trace_id = response.headers["X-Trace-ID"]

        # Filter logs from our middleware/handler
        # dispatch logs are at DEBUG level
        # root handler log is at INFO level
        related_logs = [
            log
            for log in log_sink
            if log["function"] in ("dispatch", "root") and log["extra"].get("trace_id") == trace_id
        ]

        # Expect at least:
        # 1. "Starting request with Trace ID..." (DEBUG)
        # 2. "Inside handler" (INFO)
        # 3. "Finished request with Trace ID..." (DEBUG)
        assert len(related_logs) >= 3

        for log in related_logs:
            assert log["extra"]["trace_id"] == trace_id

    finally:
        logger.remove(handler_id)
