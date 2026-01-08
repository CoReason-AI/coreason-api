from fastapi.testclient import TestClient

from coreason_api.main import app

client = TestClient(app)


def test_global_exception_handler():
    # We need to disable raise_server_exceptions to let the app handle it.

    # We create a new app instance to avoid polluting the global one?
    # Actually, we can just use the global app if we attach a route.
    # But let's be safe.
    from coreason_api.main import create_app

    test_app = create_app()

    @test_app.get("/force_error")
    def force_error():
        raise ValueError("Oops")

    safe_client = TestClient(test_app, raise_server_exceptions=False)
    response = safe_client.get("/force_error")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}


def test_hello_world():
    from coreason_api.main import hello_world

    assert hello_world() == "Hello World!"
