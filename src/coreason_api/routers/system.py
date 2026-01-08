from fastapi import APIRouter, Depends, status, HTTPException
from coreason_vault import VaultManager
from coreason_api.dependencies import get_vault_manager, get_redis_ledger
from coreason_budget.ledger import RedisLedger
from coreason_api.utils.logger import logger

router = APIRouter()

@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness():
    """Returns 200 OK if Uvicorn is running."""
    return {"status": "ok"}

@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness(
    vault: VaultManager = Depends(get_vault_manager),
    ledger: RedisLedger = Depends(get_redis_ledger)
):
    """Returns 200 OK if dependencies are reachable."""

    # Check Redis
    try:
        await ledger.connect()
    except Exception as e:
        logger.error(f"Readiness check failed (Redis): {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis unreachable")

    # Check Vault
    try:
        # We try to get a non-existent secret or just verify we can call it.
        # This allows us to mock side_effect to trigger failure path.
        vault.get_secret("health-check-dummy", default=None)
    except Exception as e:
        logger.error(f"Readiness check failed (Vault): {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Vault unreachable")

    return {"status": "ready"}
