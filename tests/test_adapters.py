from unittest.mock import patch

from coreason_api.adapters import BudgetAdapter, GatekeeperAdapter, VaultAdapter


class TestVaultAdapter:
    def test_get_secret_success(self):
        with patch("coreason_api.adapters._VaultManager") as MockVM:
            mock_manager = MockVM.return_value
            mock_manager.secrets.get_secret.return_value = "my-secret"

            adapter = VaultAdapter()
            result = adapter.get_secret("my-key")

            assert result == "my-secret"
            mock_manager.secrets.get_secret.assert_called_with("my-key")

    def test_get_secret_failure_returns_default(self):
        with patch("coreason_api.adapters._VaultManager") as MockVM:
            mock_manager = MockVM.return_value
            mock_manager.secrets.get_secret.side_effect = Exception("Not found")

            adapter = VaultAdapter()
            result = adapter.get_secret("my-key", default="default-val")

            assert result == "default-val"


class TestBudgetAdapter:
    def test_check_quota(self):
        with (
            patch("coreason_api.adapters._BudgetGuard") as MockGuard,
            patch("coreason_api.adapters.RedisLedger"),
            patch("coreason_api.adapters.CoreasonBudgetConfig"),
        ):
            mock_guard = MockGuard.return_value
            mock_guard.check.return_value = True

            adapter = BudgetAdapter("redis://local")
            # check_quota is async
            import asyncio

            result = asyncio.run(adapter.check_quota("user123", 10.5))

            assert result is True
            mock_guard.check.assert_called_with(user_id="user123", estimated_cost=10.5)


class TestGatekeeperAdapter:
    def test_init_reads_env(self):
        with (
            patch.dict("os.environ", {"SRB_PUBLIC_KEY": "pem-content"}),
            patch("coreason_api.adapters._SignatureValidator") as MockValidator,
        ):
            GatekeeperAdapter()
            MockValidator.assert_called_with(public_key_store="pem-content")
