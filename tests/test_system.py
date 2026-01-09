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
from coreason_api.main import app
from coreason_identity.manager import IdentityManager
from fastapi.testclient import TestClient


@pytest.fixture  # type: ignore[misc]
def mock_vault() -> MagicMock:
    mock = MagicMock(spec=VaultAdapter)
    mock.get_secret.return_value = "secret"
    return mock


@pytest.fixture  # type: ignore[misc]
def mock_identity() -> AsyncMock:
    mock = AsyncMock(spec=IdentityManager)
    # validate_token is async
    mock.validate_token = AsyncMock(return_value={"sub": "user123"})
    return mock


@pytest.fixture  # type: ignore[misc]
def mock_budget() -> AsyncMock:
    mock = AsyncMock(spec=BudgetAdapter)
    mock.check_quota = AsyncMock(return_value=True)
    return mock


@pytest.fixture  # type: ignore[misc]
def client(mock_vault: MagicMock, mock_identity: AsyncMock, mock_budget: AsyncMock) -> TestClient:
    app.dependency_overrides[get_vault_manager] = lambda: mock_vault
    app.dependency_overrides[get_identity_manager] = lambda: mock_identity
    app.dependency_overrides[get_budget_guard] = lambda: mock_budget
    return TestClient(app)


def test_health_live(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "details": None}


def test_health_ready_success(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "details": None}


def test_health_ready_vault_failure(client: TestClient, mock_vault: MagicMock) -> None:
    mock_vault.get_secret.side_effect = Exception("Vault connection failed")
    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["status"] == "unhealthy"
    assert "Vault connection failed" in data["detail"]["details"]["vault"]


def test_health_ready_identity_failure(client: TestClient, mock_identity: AsyncMock) -> None:
    mock_identity.validate_token.side_effect = Exception("IDP unreachable")
    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["status"] == "unhealthy"
    assert "IDP unreachable" in data["detail"]["details"]["identity"]


def test_health_ready_budget_failure(client: TestClient, mock_budget: AsyncMock) -> None:
    mock_budget.check_quota.side_effect = Exception("DB unreachable")
    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["status"] == "unhealthy"
    assert "DB unreachable" in data["detail"]["details"]["budget"]


def test_health_ready_multiple_failures(client: TestClient, mock_vault: MagicMock, mock_budget: AsyncMock) -> None:
    # Fail both Vault and Budget
    mock_vault.get_secret.side_effect = Exception("Vault Down")
    mock_budget.check_quota.side_effect = Exception("Redis Down")

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["status"] == "unhealthy"
    details = data["detail"]["details"]
    assert "Vault Down" in details["vault"]
    assert "Redis Down" in details["budget"]
    # Identity should be fine (or not in dict if skipped? logic runs all)
    assert "identity" not in details


def test_health_ready_unexpected_exception(client: TestClient, mock_identity: AsyncMock) -> None:
    # Simulate a very generic/unexpected error
    mock_identity.validate_token.side_effect = RuntimeError("Something bad happened")

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["detail"]["status"] == "unhealthy"
    assert "Something bad happened" in data["detail"]["details"]["identity"]
