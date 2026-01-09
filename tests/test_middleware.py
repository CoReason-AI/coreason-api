# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

import asyncio
from typing import Generator

import pytest
from coreason_api.middleware import TraceIDMiddleware
from coreason_api.utils.logger import logger
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)

    @app.get("/")
    async def root() -> dict[str, str]:
        logger.info("Inside handler")
        return {"message": "ok"}

    @app.get("/error")
    async def error() -> None:
        raise HTTPException(status_code=400, detail="Bad Request")

    @app.get("/sleep")
    async def sleep_handler(idx: int) -> dict[str, int]:
        logger.info(f"Sleeping request {idx}")
        await asyncio.sleep(0.1)
        logger.info(f"Waking request {idx}")
        return {"idx": idx}

    return app


@pytest.fixture
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


def test_trace_id_empty_header(client: TestClient) -> None:
    """Test that a new Trace ID is generated if the header is present but empty."""
    # Pass empty string as header value
    response = client.get("/", headers={"X-Trace-ID": ""})
    assert response.status_code == 200
    trace_id = response.headers.get("X-Trace-ID")
    assert trace_id is not None
    assert len(trace_id) > 0
    # Should be a generated UUID, definitely not empty
    assert trace_id != ""


def test_trace_id_non_uuid_header(client: TestClient) -> None:
    """Test that weird/non-UUID trace IDs are propagated (opaque token behavior)."""
    weird_id = "not-a-uuid-just-some-string"
    response = client.get("/", headers={"X-Trace-ID": weird_id})
    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == weird_id


def test_trace_id_on_handled_exception(client: TestClient) -> None:
    """
    Test that the Trace ID is present in the response headers even when
    the application returns an error response (e.g. 400).
    """
    response = client.get("/error")
    assert response.status_code == 400
    assert "X-Trace-ID" in response.headers
    assert len(response.headers["X-Trace-ID"]) > 0


@pytest.mark.anyio
async def test_trace_id_concurrency(app: FastAPI) -> None:
    """
    Test that Trace IDs are correctly isolated in concurrent async requests.
    This ensures that the `contextvars` context used by loguru does not leak
    between tasks.
    """
    log_sink = []

    def sink(message: str) -> None:
        record = message.record  # type: ignore[attr-defined]
        log_sink.append(record)

    handler_id = logger.add(sink, level="INFO")

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Fire 5 concurrent requests
            tasks = [ac.get(f"/sleep?idx={i}") for i in range(5)]
            responses = await asyncio.gather(*tasks)

        # Map response Trace IDs to their request index
        trace_map = {}
        for i, resp in enumerate(responses):
            assert resp.status_code == 200
            t_id = resp.headers["X-Trace-ID"]
            trace_map[i] = t_id

        # Verify all Trace IDs are unique
        assert len(set(trace_map.values())) == 5

        # Verify logs
        # For each request index, find the logs ("Sleeping...", "Waking...")
        # and ensure they carry the correct trace_id associated with that response
        for i, t_id in trace_map.items():
            # Find logs for this index
            req_logs = [
                log
                for log in log_sink
                if (f"Sleeping request {i}" in log["message"] or f"Waking request {i}" in log["message"])
            ]
            assert len(req_logs) == 2  # Should have sleep and wake log
            for log in req_logs:
                assert log["extra"]["trace_id"] == t_id

    finally:
        logger.remove(handler_id)
