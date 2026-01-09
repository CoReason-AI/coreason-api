from fastapi.testclient import TestClient

from coreason_api.main import app

# raise_server_exceptions=False needed to test 500 handler
client = TestClient(app, raise_server_exceptions=False)


def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_global_exception_handler():
    # Adding a test route dynamically
    @app.get("/force-error")
    def force_error():
        raise ValueError("Something went wrong")

    response = client.get("/force-error")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error. Please contact support."}


def test_middleware_integrated():
    response = client.get("/health/live")
    assert "X-Trace-ID" in response.headers
