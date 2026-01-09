# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from coreason_api.config import Settings
from coreason_api.dependencies import (
    get_auditor,
    get_budget_guard,
    get_gatekeeper,
    get_identity_manager,
    get_manifest_validator,
    get_session_manager,
    get_vault_manager,
)


def test_get_vault_manager() -> None:
    # Patch the class where it is imported in dependencies.py
    with patch("coreason_api.dependencies.VaultManager") as MockVault:
        get_vault_manager.cache_clear()

        instance1 = get_vault_manager()
        instance2 = get_vault_manager()

        assert instance1 is instance2
        MockVault.assert_called_once()


def test_get_identity_manager_with_real_settings() -> None:
    """
    Verify that get_identity_manager works with a real Settings object
    to ensure hashability (frozen=True).
    """
    settings = Settings()

    with patch("coreason_api.dependencies.IdentityManager") as MockIdentity:
        get_identity_manager.cache_clear()

        # Should not raise TypeError: unhashable type: 'Settings'
        instance1 = get_identity_manager(settings)
        instance2 = get_identity_manager(settings)

        assert instance1 is instance2
        MockIdentity.assert_called_once()


def test_get_identity_manager_configuration() -> None:
    mock_settings = MagicMock()
    mock_settings.COREASON_AUTH_DOMAIN = "test.auth"
    mock_settings.COREASON_AUTH_AUDIENCE = "test.aud"
    mock_settings.COREASON_AUTH_CLIENT_ID = "test-client"

    with (
        patch("coreason_api.dependencies.IdentityManager") as MockIdentity,
        patch("coreason_api.dependencies.CoreasonIdentityConfig") as MockConfig,
    ):
        get_identity_manager.cache_clear()

        instance1 = get_identity_manager(mock_settings)
        instance2 = get_identity_manager(mock_settings)

        assert instance1 is instance2

        # Verify Config was created with settings
        MockConfig.assert_called_with(domain="test.auth", audience="test.aud", client_id="test-client")
        # Verify Manager was created with config
        MockIdentity.assert_called_once_with(config=MockConfig.return_value)


def test_get_identity_manager_invalid_config() -> None:
    """
    Edge Case: Settings provide invalid values for Identity Config.
    """
    mock_settings = MagicMock()
    # Missing required fields or invalid types might trigger ValidationError
    # Here we assume CoreasonIdentityConfig raises ValidationError if validation fails.
    # We force validation error by simulating it.

    with (
        patch(
            "coreason_api.dependencies.CoreasonIdentityConfig",
            side_effect=ValidationError.from_exception_data("Config", []),
        ),
    ):
        get_identity_manager.cache_clear()

        with pytest.raises(ValidationError):
            get_identity_manager(mock_settings)


def test_get_budget_guard() -> None:
    mock_settings = MagicMock()
    mock_settings.DATABASE_URL = "sqlite:///:memory:"

    with patch("coreason_api.dependencies.BudgetGuard") as MockBudget:
        get_budget_guard.cache_clear()

        instance1 = get_budget_guard(mock_settings)
        instance2 = get_budget_guard(mock_settings)

        assert instance1 is instance2
        MockBudget.assert_called_once_with(db_url="sqlite:///:memory:")


def test_get_auditor() -> None:
    with patch("coreason_api.dependencies.Auditor") as MockAuditor:
        get_auditor.cache_clear()

        instance1 = get_auditor()
        instance2 = get_auditor()

        assert instance1 is instance2
        MockAuditor.assert_called_once_with(service_name="coreason-api")


def test_get_gatekeeper() -> None:
    mock_settings = MagicMock()
    mock_settings.SRB_PUBLIC_KEY = "mock-key-store"

    with patch("coreason_api.dependencies.Gatekeeper") as MockGatekeeper:
        get_gatekeeper.cache_clear()

        instance1 = get_gatekeeper(mock_settings)
        instance2 = get_gatekeeper(mock_settings)

        assert instance1 is instance2
        MockGatekeeper.assert_called_once_with(public_key_store="mock-key-store")


def test_get_gatekeeper_invalid_key() -> None:
    """
    Edge Case: Invalid Public Key causes Gatekeeper initialization failure.
    """
    mock_settings = MagicMock()
    mock_settings.SRB_PUBLIC_KEY = "invalid-key"

    # Simulate Gatekeeper (SignatureValidator) raising ValueError on bad key
    with patch("coreason_api.dependencies.Gatekeeper", side_effect=ValueError("Invalid key")):
        get_gatekeeper.cache_clear()

        with pytest.raises(ValueError, match="Invalid key"):
            get_gatekeeper(mock_settings)


def test_get_session_manager() -> None:
    with patch("coreason_api.dependencies.SessionManager") as MockSession:
        get_session_manager.cache_clear()

        instance1 = get_session_manager()
        instance2 = get_session_manager()

        assert instance1 is instance2
        MockSession.assert_called_once()


def test_get_manifest_validator() -> None:
    with patch("coreason_api.dependencies.ManifestValidator") as MockValidator:
        get_manifest_validator.cache_clear()

        instance1 = get_manifest_validator()
        instance2 = get_manifest_validator()

        assert instance1 is instance2
        MockValidator.assert_called_once()
