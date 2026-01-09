from coreason_api.adapters import BudgetGuard, IdentityManager
from coreason_api.config import Settings
from coreason_api.dependencies import get_budget, get_identity


def test_get_identity():
    settings = Settings(AUTH0_DOMAIN="test.domain", AUTH0_AUDIENCE="test.aud")
    identity = get_identity(settings)
    assert isinstance(identity, IdentityManager)
    # Verify config was passed correctly if we can inspect it
    # Since IdentityAdapter wraps IdentityManager, and we alias it...
    # logic is in dependencies.py


def test_get_budget():
    settings = Settings(REDIS_URL="redis://test")
    budget = get_budget(settings)
    assert isinstance(budget, BudgetGuard)
    assert budget.config.redis_url == "redis://test"
