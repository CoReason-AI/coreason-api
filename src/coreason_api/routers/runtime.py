# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

import uuid
from typing import Annotated, Any, Dict, Optional

from coreason_identity.manager import IdentityManager
from coreason_veritas.auditor import IERLogger as Auditor
from coreason_veritas.exceptions import ComplianceViolationError
from coreason_veritas.gatekeeper import PolicyGuard
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from coreason_api.adapters import BudgetAdapter, MCPAdapter
from coreason_api.dependencies import (
    get_auditor,
    get_budget_guard,
    get_identity_manager,
    get_policy_guard,
    get_session_manager,
)
from coreason_api.utils.logger import logger

router = APIRouter(tags=["runtime"])


class RunRequest(BaseModel):
    input_data: Dict[str, Any]
    session_context: Optional[Dict[str, Any]] = None
    cost_estimate: float = Field(default=1.0, ge=0.0)  # Default cost unit if not specified


class RunResponse(BaseModel):
    result: Any
    transaction_id: str


@router.post("/v1/run/{agent_id}", response_model=RunResponse)
async def run_agent(
    agent_id: str,
    request: RunRequest,
    background_tasks: BackgroundTasks,
    authorization: Annotated[Optional[str], Header()] = None,
    identity: IdentityManager = Depends(get_identity_manager),  # noqa: B008
    policy_guard: PolicyGuard = Depends(get_policy_guard),  # noqa: B008
    budget: BudgetAdapter = Depends(get_budget_guard),  # noqa: B008
    auditor: Auditor = Depends(get_auditor),  # noqa: B008
    mcp: MCPAdapter = Depends(get_session_manager),  # noqa: B008
) -> RunResponse:
    """
    Execute an agent via the Production Runtime.
    Enforces the Chain of Command:
    1. Tracing (Middleware)
    2. Authentication
    3. Policy Check
    4. Budget Check
    5. Audit Start
    6. Execution
    7. Settlement
    8. Audit End
    """
    # 2. Authentication
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    try:
        user_context = await identity.validate_token(authorization)
    except Exception as e:
        logger.warning(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        ) from e

    # Fix: UserContext uses 'sub', not 'user_id'
    user_id = user_context.sub

    # 3. Policy Check
    try:
        # Convert Pydantic UserContext to Dict for PolicyGuard
        # Using model_dump() if available (Pydantic v2), else dict()
        user_ctx_dict = user_context.model_dump()
        policy_guard.verify_access(agent_id=agent_id, user_context=user_ctx_dict)
    except ComplianceViolationError as e:
        logger.warning(f"Policy Violation: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Policy violation: {e}",
        ) from e
    except Exception as e:
        logger.error(f"Policy check failed unexpectedly: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Policy check failed",
        ) from e

    # 4. Budget Check
    try:
        allowed = await budget.check_quota(user_id=user_id, cost_estimate=request.cost_estimate)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient quota",
            )
    except Exception as e:
        # If it's the 402 we just raised, re-raise it.
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Budget check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking budget",
        ) from e

    # 5. Audit Start
    try:
        await auditor.log_event(
            "EXECUTION_START",
            {
                "agent_id": agent_id,
                "user_id": user_id,
                "cost_estimate": request.cost_estimate,
            },
        )
    except Exception as e:
        logger.error(f"Audit start log failed: {e}")
        # Proceeding despite audit failure? PRD says "Immutable Auditing".
        # Ideally we should fail if we can't audit, for strict GxP compliance.
        # But failing hard might be too aggressive if audit service is temporary down.
        # Given "The Conductor... enforces... Immutable Auditing", I'll be strict.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Audit logging failed",
        ) from e

    # 6. Execution
    try:
        # Merge request context with user info
        ctx_data = request.session_context or {}
        ctx_data["user_id"] = user_id

        # Since SessionContext is not importable, we pass the dict directly.
        # The execute_agent signature accepts `context: Any`.
        session_ctx = ctx_data

        result = await mcp.execute_agent(agent_id=agent_id, input_data=request.input_data, context=session_ctx)
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        # Still need to log Audit End (Failure)? PRD says "Audit End: Log completion".
        # Should we charge for failed execution? Usually depends on policy.
        # Assuming "Settlement" happens after execution.
        await auditor.log_event(
            "EXECUTION_FAILED",
            {"agent_id": agent_id, "user_id": user_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}",
        ) from e

    # 7. Settlement (Fire-and-Forget)
    # Using BackgroundTasks for fire-and-forget
    background_tasks.add_task(
        budget.record_transaction,
        user_id=user_id,
        amount=request.cost_estimate,  # Or actual cost if result provides it?
        context={"agent_id": agent_id, "transaction_type": "agent_execution"},
    )

    # 8. Audit End
    # This should probably be awaited to ensure it's recorded before returning response?
    # PRD lists it as step 8.
    try:
        await auditor.log_event(
            "EXECUTION_END",
            {"agent_id": agent_id, "user_id": user_id, "status": "success"},
        )
    except Exception as e:
        logger.error(f"Audit end log failed: {e}")
        # We don't fail the request here since execution succeeded.

    return RunResponse(
        result=result,
        transaction_id=str(uuid.uuid4()),  # Generate a transaction ID or get from result?
    )
