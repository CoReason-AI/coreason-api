from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from coreason_api.adapters import BudgetGuard, VaultManager
from coreason_api.dependencies import get_budget, get_vault
from coreason_api.routers import system

# Mock dependencies
app = FastAPI()
app.include_router(system.router)

client = TestClient(app)


def test_liveness():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_success():
    # We need to override dependencies to ensure they don't fail during test
    app.dependency_overrides[get_vault] = lambda: MagicMock(spec=VaultManager)
    app.dependency_overrides[get_budget] = lambda: MagicMock(spec=BudgetGuard)

    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

    app.dependency_overrides = {}
