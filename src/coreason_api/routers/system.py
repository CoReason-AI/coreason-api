# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from coreason_budget.ledger import RedisLedger
from coreason_vault import VaultManager
from fastapi import APIRouter, Depends, HTTPException, status

from coreason_api.dependencies import get_redis_ledger, get_vault_manager
from coreason_api.utils.logger import logger

router = APIRouter()


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness() -> dict[str, str]:
    """Returns 200 OK if Uvicorn is running."""
    return {"status": "ok"}


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness(
    vault: VaultManager = Depends(get_vault_manager), ledger: RedisLedger = Depends(get_redis_ledger)
) -> dict[str, str]:
    """Returns 200 OK if dependencies are reachable."""

    # Check Redis
    try:
        await ledger.connect()
    except Exception as e:
        logger.error(f"Readiness check failed (Redis): {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis unreachable") from e

    # Check Vault
    try:
        # We try to get a non-existent secret or just verify we can call it.
        # This allows us to mock side_effect to trigger failure path.
        vault.get_secret("health-check-dummy", default=None)
    except Exception as e:
        logger.error(f"Readiness check failed (Vault): {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Vault unreachable") from e

    return {"status": "ready"}
