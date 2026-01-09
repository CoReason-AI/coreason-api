from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from coreason_api.middleware import TraceIDMiddleware


def test_trace_id_middleware_adds_header():
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)

    @app.get("/")
    def read_root():
        return {"Hello": "World"}

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "X-Trace-ID" in response.headers
    assert len(response.headers["X-Trace-ID"]) > 0


def test_trace_id_middleware_preserves_header():
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)

    @app.get("/")
    def read_root(request: Request):
        return {"trace_id": request.headers.get("X-Trace-ID")}

    client = TestClient(app)
    trace_id = "test-trace-id-123"
    response = client.get("/", headers={"X-Trace-ID": trace_id})
    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == trace_id
    assert response.json()["trace_id"] == trace_id
