
import pytest
from fastapi.testclient import TestClient
from coreason_api.main import app
from unittest.mock import patch

client = TestClient(app)

def test_global_exception_handler():
    # We need to trigger a 500 error.
    # The previous attempt failed because TestClient raises the exception if it's not handled?
    # No, TestClient normally catches exceptions if they are handled by app.
    # The traceback shows `ValueError: Oops` bubbling up.
    # This means `app` did NOT catch it?
    # Or `TestClient` is configured to raise_server_exceptions=True by default?
    # Yes, Starlette TestClient raises server exceptions by default.

    # We need to disable that.

    client_safe = TestClient(app, raise_server_exceptions=False)

    # We patch a route onto the app temporarily.
    # But since app is global in main.py, we might pollute it.
    # Better to create a new app instance or clean up.
    # But `create_app` is available.

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
