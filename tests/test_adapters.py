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


@pytest.mark.anyio
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
