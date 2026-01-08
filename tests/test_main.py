# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from coreason_identity.models import UserContext
from coreason_mcp.session_manager import SessionManager
from coreason_veritas.anchor import DeterminismInterceptor as TrustAnchor
from coreason_veritas.auditor import IERLogger as Auditor
from coreason_veritas.gatekeeper import SignatureValidator as Gatekeeper
from fastapi.testclient import TestClient

from coreason_api.dependencies import (
    get_auditor,
    get_budget_guard,
    get_gatekeeper,
    get_identity_manager,
    get_redis_ledger,
    get_session_manager,
)
from coreason_api.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    # Using context manager to ensure lifespan events run
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def mock_deps() -> dict[str, Any]:
    # Setup all mocks
    identity = MagicMock()
    user = UserContext(sub="user-1", email="test@test.com", project_context="proj-1", permissions=[])
    identity.validate_token.return_value = user

    budget = AsyncMock()
    budget.check.return_value = True
    budget.connect.return_value = None  # For readiness

    gatekeeper = MagicMock(spec=Gatekeeper)
    auditor = MagicMock(spec=Auditor)
    session = MagicMock(spec=SessionManager)
    trust_anchor = MagicMock(spec=TrustAnchor)
    ledger = AsyncMock()

    return {
        "identity": identity,
        "budget": budget,
        "gatekeeper": gatekeeper,
        "auditor": auditor,
        "session": session,
        "trust_anchor": trust_anchor,
        "ledger": ledger,
    }


def test_health_check(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_check(client: TestClient, mock_deps: dict[str, Any]) -> None:
    app.dependency_overrides[get_redis_ledger] = lambda: mock_deps["ledger"]
    response = client.get("/health/ready")
    assert response.status_code == 200
    app.dependency_overrides = {}


def test_global_exception_handler(client: TestClient) -> None:
    # Route that triggers unhandled exception

    # We define a temporary route on the app to force an exception
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/force-error")
    def force_error() -> None:
        raise ValueError("Boom")

    app.include_router(router)

    response = client.get("/force-error")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal Server Error"


def test_full_flow_integration(client: TestClient, mock_deps: dict[str, Any]) -> None:
    # Test one full flow through main app entry point
    app.dependency_overrides[get_identity_manager] = lambda: mock_deps["identity"]
    app.dependency_overrides[get_budget_guard] = lambda: mock_deps["budget"]
    app.dependency_overrides[get_gatekeeper] = lambda: mock_deps["gatekeeper"]
    app.dependency_overrides[get_auditor] = lambda: mock_deps["auditor"]
    app.dependency_overrides[get_session_manager] = lambda: mock_deps["session"]

    response = client.post(
        "/v1/run/agent-main", json={"input_data": {}, "estimated_cost": 1.0}, headers={"Authorization": "Bearer valid"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert "X-Trace-ID" in response.headers

    app.dependency_overrides = {}
