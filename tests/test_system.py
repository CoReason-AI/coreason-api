# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from unittest.mock import AsyncMock, MagicMock

import pytest
from coreason_api.adapters import BudgetAdapter, VaultAdapter
from coreason_api.dependencies import get_budget_guard, get_identity_manager, get_vault_manager
from coreason_api.routers.system import router
from coreason_identity.manager import IdentityManager
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def mock_vault() -> MagicMock:
    mock = MagicMock(spec=VaultAdapter)
    mock.get_secret.return_value = "ok"
    return mock


@pytest.fixture
def mock_identity() -> MagicMock:
    mock = MagicMock(spec=IdentityManager)
    # validate_token is async
    mock.validate_token = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def mock_budget() -> MagicMock:
    mock = MagicMock(spec=BudgetAdapter)
    mock.check_quota = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def client(mock_vault: MagicMock, mock_identity: MagicMock, mock_budget: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_vault_manager] = lambda: mock_vault
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_budget_guard] = lambda: mock_budget

    return TestClient(app)


def test_liveness_check(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "details": None}


def test_readiness_check_success(
    client: TestClient, mock_vault: MagicMock, mock_identity: MagicMock, mock_budget: MagicMock
) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "details": None}

    mock_vault.get_secret.assert_called_with("health_check_probe", default="ok")
    mock_identity.validate_token.assert_called_with("health_probe")
    mock_budget.check_quota.assert_called_with(user_id="health_probe", cost_estimate=0.0)


def test_readiness_check_failure(client: TestClient, mock_vault: MagicMock) -> None:
    # Simulate Vault failure
    mock_vault.get_secret.side_effect = Exception("Vault Down")

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["status"] == "unhealthy"
    assert "vault" in data["detail"]["details"]
    assert data["detail"]["details"]["vault"] == "Vault Down"


def test_readiness_check_all_failures(
    client: TestClient, mock_vault: MagicMock, mock_identity: MagicMock, mock_budget: MagicMock
) -> None:
    mock_vault.get_secret.side_effect = Exception("Vault Down")
    mock_identity.validate_token.side_effect = Exception("Identity Down")
    mock_budget.check_quota.side_effect = Exception("Budget Down")

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert "vault" in data["detail"]["details"]
    assert "identity" in data["detail"]["details"]
    assert "budget" in data["detail"]["details"]
