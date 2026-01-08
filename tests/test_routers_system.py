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
from fastapi import FastAPI
from fastapi.testclient import TestClient

from coreason_api.dependencies import get_redis_ledger, get_vault_manager
from coreason_api.routers.system import router

app = FastAPI()
app.include_router(router)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_liveness(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_success(client: TestClient) -> None:
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


def test_readiness_failure_redis(client: TestClient) -> None:
    mock_ledger = AsyncMock()
    mock_ledger.connect.side_effect = Exception("Redis down")

    app.dependency_overrides[get_redis_ledger] = lambda: mock_ledger

    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "Redis unreachable"
    app.dependency_overrides = {}


def test_readiness_failure_vault(client: TestClient) -> None:
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
