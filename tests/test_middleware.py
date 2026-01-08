import pytest
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from coreason_api.middleware import TraceIDMiddleware

def test_trace_id_middleware_generates_id():
    app = Starlette()
    app.add_middleware(TraceIDMiddleware)

    @app.route("/")
    async def homepage(request):
        return JSONResponse({"trace_id": request.state.trace_id})

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "X-Trace-ID" in response.headers
    trace_id = response.headers["X-Trace-ID"]
    assert len(trace_id) > 0
    assert response.json()["trace_id"] == trace_id

def test_trace_id_middleware_preserves_id():
    app = Starlette()
    app.add_middleware(TraceIDMiddleware)

    @app.route("/")
    async def homepage(request):
        return JSONResponse({"trace_id": request.state.trace_id})

    client = TestClient(app)
    custom_trace_id = "12345-custom-id"
    response = client.get("/", headers={"X-Trace-ID": custom_trace_id})

    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == custom_trace_id
    assert response.json()["trace_id"] == custom_trace_id
