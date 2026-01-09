# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from typing import Annotated, Dict, Optional

from coreason_identity.manager import IdentityManager
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from coreason_api.adapters import BudgetAdapter, VaultAdapter
from coreason_api.dependencies import get_budget_guard, get_identity_manager, get_vault_manager
from coreason_api.utils.logger import logger

router = APIRouter(tags=["system"])


class HealthStatus(BaseModel):  # type: ignore[misc]
    status: str
    details: Optional[Dict[str, str]] = None


@router.get("/health/live", response_model=HealthStatus)
async def liveness_check() -> HealthStatus:
    """
    Liveness probe: Checks if the application is running.
    """
    return HealthStatus(status="ok")


@router.get("/health/ready", response_model=HealthStatus)
async def readiness_check(
    vault: Annotated[VaultAdapter, Depends(get_vault_manager)],
    identity: Annotated[IdentityManager, Depends(get_identity_manager)],
    budget: Annotated[BudgetAdapter, Depends(get_budget_guard)],
) -> HealthStatus:
    """
    Readiness probe: Checks connectivity to critical dependencies.
    """
    errors: Dict[str, str] = {}

    # Check Vault
    try:
        # Use lightweight secret fetch via Adapter (which exposes .get_secret)
        _ = vault.get_secret("health_check_probe", default="ok")
    except Exception as e:
        logger.error(f"Readiness Check Failed: Vault unreachable. Error: {e}")
        errors["vault"] = str(e)

    # Check Identity Provider
    try:
        # Validate a dummy token. Expecting generic error, but connectivity check.
        _ = await identity.validate_token("health_probe")
    except Exception as e:
        logger.error(f"Readiness Check Failed: Identity Provider error. Error: {e}")
        errors["identity"] = str(e)

    # Check Budget (Database/Redis)
    try:
        # Lightweight check: Check quota for dummy user via Adapter
        # Adapter exposes check_quota(user_id, cost_estimate)
        _ = await budget.check_quota(user_id="health_probe", cost_estimate=0.0)
    except Exception as e:
        logger.error(f"Readiness Check Failed: Budget Service error. Error: {e}")
        errors["budget"] = str(e)

    if errors:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "unhealthy", "details": errors},
        )

    return HealthStatus(status="ready")
