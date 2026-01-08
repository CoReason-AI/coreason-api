from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure mocks are reset
# Note: In a real scenario we'd use a better mocking strategy,
# but here we rely on sys.modules patching in conftest + manual resets.


def test_liveness_probe():
    from coreason_api.routers.system import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_probe():
    # We need to mock dependencies
    with patch("coreason_api.dependencies.get_vault_manager") as mock_get_vault:
        with patch("coreason_api.dependencies.get_identity_manager") as mock_get_identity:
            mock_vault = MagicMock()
            mock_identity = MagicMock()

            mock_get_vault.return_value = mock_vault
            mock_get_identity.return_value = mock_identity

            from coreason_api.routers.system import router

            app = FastAPI()
            app.include_router(router)

            # Override dependencies in the app
            # app.dependency_overrides is better than patching the provider function?
            # Yes, standard FastAPI testing practice.

            # Let's do it the standard way.
            pass


def test_readiness_probe_standard_way():
    from coreason_api.dependencies import get_identity_manager, get_vault_manager
    from coreason_api.routers.system import router

    app = FastAPI()
    app.include_router(router)

    mock_vault = MagicMock()
    mock_identity = MagicMock()

    app.dependency_overrides[get_vault_manager] = lambda: mock_vault
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity

    client = TestClient(app)

    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
