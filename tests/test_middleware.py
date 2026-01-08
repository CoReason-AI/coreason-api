
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from coreason_api.middleware import TraceIDMiddleware

def test_trace_id_middleware_generates_id():
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)

    @app.get("/ping")
    def ping():
        return {"ping": "pong"}

    client = TestClient(app)
    response = client.get("/ping")

    assert response.status_code == 200
    assert "X-Trace-ID" in response.headers
    assert len(response.headers["X-Trace-ID"]) > 0

def test_trace_id_middleware_preserves_id():
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)

    @app.get("/ping")
    def ping():
        return {"ping": "pong"}

    client = TestClient(app)
    custom_id = "custom-trace-id-123"
    response = client.get("/ping", headers={"X-Trace-ID": custom_id})

    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == custom_id
