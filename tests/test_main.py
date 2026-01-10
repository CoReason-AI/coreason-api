# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from unittest.mock import patch

from coreason_api.main import app, hello_world
from fastapi.testclient import TestClient


def test_hello_world() -> None:
    # Test the standalone function (likely a leftover, but verified for completeness)
    assert hello_world() == "Hello World!"


def test_app_lifespan() -> None:
    with TestClient(app) as client:
        # Trigger lifespan startup/shutdown
        response = client.get("/health/live")
        assert response.status_code == 200


def test_routers_included() -> None:
    # Patch where BudgetAdapter is used to avoid validation error on init
    with patch("coreason_api.adapters.CoreasonBudgetConfig"):
        client = TestClient(app)

        # Check System Router
        assert client.get("/health/live").status_code == 200

        # Check Runtime Router
        # 422 because input_data is missing, which proves the endpoint is reached and validation is running
        assert client.post("/v1/run/test", json={}).status_code == 422

        # Check Runtime Router with valid body but missing auth
        assert client.post("/v1/run/test", json={"input_data": {}}).status_code == 401

        # Check Architect Router (prompt required)
        assert client.post("/v1/architect/generate", json={}).status_code == 422
