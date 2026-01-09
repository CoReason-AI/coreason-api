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
    # Patch VaultAdapter instead of VaultManager
    with (
        patch("coreason_api.dependencies.VaultAdapter") as MockVM,
        patch("coreason_api.dependencies.CoreasonVaultConfig"),
    ):
        vm = get_vault_manager()
        assert vm is MockVM.return_value
        MockVM.assert_called_once()


def test_get_identity_manager() -> None:
    mock_settings = MagicMock()
    mock_settings.COREASON_AUTH_DOMAIN = "d"
    mock_settings.COREASON_AUTH_AUDIENCE = "a"
    mock_settings.COREASON_AUTH_CLIENT_ID = "c"

    with patch("coreason_api.dependencies.IdentityManager") as MockIM:
        im = get_identity_manager(mock_settings)
        assert im is MockIM.return_value
        # Check config passed
        args, kwargs = MockIM.call_args
        config = kwargs["config"]
        assert config.domain == "d"


def test_get_budget_guard() -> None:
    mock_settings = MagicMock()
    mock_settings.REDIS_URL = "redis://localhost:6379/0"

    # Patch BudgetAdapter instead of BudgetGuard
    with (
        patch("coreason_api.dependencies.BudgetAdapter") as MockBG,
    ):
        bg = get_budget_guard(mock_settings)
        assert bg is MockBG.return_value
        # Check call args if needed
        MockBG.assert_called_with(db_url="redis://localhost:6379/0")


def test_get_auditor() -> None:
    with patch("coreason_api.dependencies.Auditor") as MockAuditor:
        auditor = get_auditor()
        assert auditor is MockAuditor.return_value
        MockAuditor.assert_called_with(service_name="coreason-api")


def test_get_gatekeeper() -> None:
    mock_settings = MagicMock()
    mock_settings.SRB_PUBLIC_KEY = "dummy-pem"

    with patch("coreason_api.dependencies.Gatekeeper") as MockGK:
        gk = get_gatekeeper(mock_settings)
        assert gk is MockGK.return_value
        MockGK.assert_called_with(public_key_store="dummy-pem")


def test_get_session_manager() -> None:
    with patch("coreason_api.dependencies.SessionManager") as MockSM:
        sm = get_session_manager()
        assert sm is MockSM.return_value


def test_get_manifest_validator() -> None:
    with patch("coreason_api.dependencies.ManifestValidator") as MockMV:
        mv = get_manifest_validator()
        assert mv is MockMV.return_value
