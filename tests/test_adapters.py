# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from coreason_api.adapters import BudgetAdapter, VaultAdapter


def test_vault_adapter() -> None:
    # Test VaultAdapter delegates to internal manager
    mock_config = MagicMock()
    with patch("coreason_api.adapters.VaultManager") as MockVM:
        mock_vm_instance = MockVM.return_value
        mock_vm_instance.secrets = MagicMock()
        mock_vm_instance.secrets.get_secret.return_value = "secret_val"

        adapter = VaultAdapter(config=mock_config)
        result = adapter.get_secret("key", default="def")

        assert result == "secret_val"
        mock_vm_instance.secrets.get_secret.assert_called_with("key", default="def")


def test_vault_adapter_defaults() -> None:
    # Test VaultAdapter returns default when key missing
    mock_config = MagicMock()
    with patch("coreason_api.adapters.VaultManager") as MockVM:
        mock_vm_instance = MockVM.return_value
        mock_vm_instance.secrets = MagicMock()
        mock_vm_instance.secrets.get_secret.return_value = None

        adapter = VaultAdapter(config=mock_config)
        # Assuming internal get_secret returns the default value if key missing,
        # or we rely on the internal manager's behavior.
        # Here we mock the internal manager returning None (or we can mock it returning default)

        # Scenario: Internal manager returns default passed to it
        mock_vm_instance.secrets.get_secret.side_effect = lambda k, default: default

        result = adapter.get_secret("missing_key", default="my_default")
        assert result == "my_default"


def test_vault_adapter_error() -> None:
    # Test VaultAdapter propagates exceptions
    mock_config = MagicMock()
    with patch("coreason_api.adapters.VaultManager") as MockVM:
        mock_vm_instance = MockVM.return_value
        mock_vm_instance.secrets = MagicMock()
        mock_vm_instance.secrets.get_secret.side_effect = Exception("Vault Error")

        adapter = VaultAdapter(config=mock_config)
        with pytest.raises(Exception, match="Vault Error"):
            adapter.get_secret("key")


@pytest.mark.anyio  # type: ignore[misc]
async def test_budget_adapter() -> None:
    # Test BudgetAdapter delegates to internal guard
    with (
        patch("coreason_api.adapters.BudgetGuard") as MockBG,
        patch("coreason_api.adapters.RedisLedger"),
        patch("coreason_api.adapters.CoreasonBudgetConfig"),
    ):
        mock_bg_instance = MockBG.return_value
        mock_bg_instance.check = AsyncMock(return_value=True)
        mock_bg_instance.charge = AsyncMock()

        adapter = BudgetAdapter(db_url="redis://foo")

        # Test check_quota
        res = await adapter.check_quota("user", 10.0)
        assert res is True
        mock_bg_instance.check.assert_called_with(user_id="user", cost=10.0)

        # Test record_transaction
        await adapter.record_transaction("user", 5.0, {})
        mock_bg_instance.charge.assert_called_with(user_id="user", cost=5.0)


@pytest.mark.anyio  # type: ignore[misc]
async def test_budget_adapter_quota_exceeded() -> None:
    # Test check_quota returns False
    with (
        patch("coreason_api.adapters.BudgetGuard") as MockBG,
        patch("coreason_api.adapters.RedisLedger"),
        patch("coreason_api.adapters.CoreasonBudgetConfig"),
    ):
        mock_bg_instance = MockBG.return_value
        mock_bg_instance.check = AsyncMock(return_value=False)

        adapter = BudgetAdapter(db_url="redis://foo")
        res = await adapter.check_quota("user", 1000000.0)
        assert res is False


@pytest.mark.anyio  # type: ignore[misc]
async def test_budget_adapter_charge_failure() -> None:
    # Test record_transaction propagates errors
    with (
        patch("coreason_api.adapters.BudgetGuard") as MockBG,
        patch("coreason_api.adapters.RedisLedger"),
        patch("coreason_api.adapters.CoreasonBudgetConfig"),
    ):
        mock_bg_instance = MockBG.return_value
        mock_bg_instance.charge = AsyncMock(side_effect=Exception("Redis Down"))

        adapter = BudgetAdapter(db_url="redis://foo")
        with pytest.raises(Exception, match="Redis Down"):
            await adapter.record_transaction("user", 5.0, {})
