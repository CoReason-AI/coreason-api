from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from coreason_api.dependencies import get_redis_ledger, get_vault_manager
from coreason_api.routers.system import router

app = FastAPI()
app.include_router(router)


@pytest.fixture
def client():
    return TestClient(app)


def test_liveness(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_success(client):
    mock_ledger = AsyncMock()
    mock_ledger.connect.return_value = None
    mock_vault = MagicMock()

    app.dependency_overrides[get_redis_ledger] = lambda: mock_ledger
    app.dependency_overrides[get_vault_manager] = lambda: mock_vault

    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

    mock_ledger.connect.assert_called_once()
    mock_vault.get_secret.assert_called()
    app.dependency_overrides = {}


def test_readiness_failure_redis(client):
    mock_ledger = AsyncMock()
    mock_ledger.connect.side_effect = Exception("Redis down")

    app.dependency_overrides[get_redis_ledger] = lambda: mock_ledger

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "Redis unreachable"
    app.dependency_overrides = {}


def test_readiness_failure_vault(client):
    mock_ledger = AsyncMock()
    mock_ledger.connect.return_value = None
    mock_vault = MagicMock()
    mock_vault.get_secret.side_effect = Exception("Vault down")

    app.dependency_overrides[get_redis_ledger] = lambda: mock_ledger
    app.dependency_overrides[get_vault_manager] = lambda: mock_vault

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "Vault unreachable"
    app.dependency_overrides = {}
