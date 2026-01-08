from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel

from coreason_api.dependencies import (
    IdentityDep, BudgetDep, AuditorDep, SessionDep, SettingsDep
)
# We assume types for the mocked packages
from coreason_identity.models import UserContext
from coreason_mcp.types import SessionContext

router = APIRouter(prefix="/v1", tags=["runtime"])

class RunRequest(BaseModel):
    input_data: Dict[str, Any]
    context: Dict[str, Any] = {}

class RunResponse(BaseModel):
    result: Any
    trace_id: str

@router.post("/run/{agent_id}", response_model=RunResponse)
async def run_agent(
    agent_id: str,
    request_body: RunRequest,
    request: Request,
    identity: IdentityDep,
    budget: BudgetDep,
    auditor: AuditorDep,
    session_manager: SessionDep,
    background_tasks: BackgroundTasks,
):
    # 1. Tracing is handled by Middleware, but we can grab it.
    trace_id = getattr(request.state, "trace_id", "unknown")

    # 2. Authentication
    # The VID says: user = await identity.validate_token(auth_header)
    # Usually we extract header.
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    try:
        user: UserContext = await identity.validate_token(auth_header)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {e}")

    # 3. Policy Check (Optional Explicit)
    # PRD says: "Verify agent access via coreason-veritas (optional explicit check)."
    # VID for veritas has Gatekeeper but doesn't show an "verify_access" method explicitly
    # except `get_policy_instruction_for_llm`.
    # Maybe we skip or implement if we find a method.
    # PRD 2.1.3 says "Verify agent access".
    # If no method in VID, we might assume it's part of identity or we skip.
    # Let's check VID again in PRD.
    # VID: Auditor, Gatekeeper, TrustAnchor.
    # Gatekeeper usage: rules = Gatekeeper().get_policy_instruction_for_llm()
    # It doesn't show an access check method.
    # However, `identity.validate_token` returns `UserContext`. Maybe permissions are there.
    # Let's proceed with what we have.

    # 4. Budget Check
    # PRD: Verify user quota via coreason-budget. Reject (402) if insufficient.
    # VID: allowed = await budget.check_quota(user_id, cost_estimate)
    # We need a cost estimate. Hardcode or derive?
    estimated_cost = 1.0 # Placeholder

    try:
        if not await budget.check_quota(user.user_id, estimated_cost):
             raise HTTPException(status_code=402, detail="Insufficient funds")
    except Exception as e:
        # If check_quota raises, handle it
        if isinstance(e, HTTPException): raise e
        # If external error
        raise HTTPException(status_code=500, detail=f"Budget check failed: {e}")

    # 5. Audit Start
    # VID: await auditor.log_event("EXECUTION_START", ...)
    await auditor.log_event(
        "EXECUTION_START",
        user_id=user.user_id,
        agent_id=agent_id,
        trace_id=trace_id,
        input_hash=str(hash(str(request_body.input_data))) # Simple hash
    )

    # 6. Execution
    # VID: result = await mcp.execute_agent(agent_id, input_data, context)
    # We need to construct SessionContext or pass dict? VID says `SessionContext` type exists.
    # But `execute_agent` usage shows `context` passed as arg.
    # Let's pass the dictionary.

    # We should probably mix request context with user info.
    execution_context = SessionContext(
        user_id=user.user_id,
        trace_id=trace_id,
        **request_body.context
    )

    try:
        result = await session_manager.execute_agent(
            agent_id,
            request_body.input_data,
            execution_context
        )
    except Exception as e:
        # Audit failure?
        await auditor.log_event(
            "EXECUTION_FAILED",
            user_id=user.user_id,
            agent_id=agent_id,
            trace_id=trace_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Execution failed: {e}")

    # 7. Settlement
    # PRD: Deduct cost via coreason-budget (fire-and-forget).
    # We use BackgroundTasks for fire-and-forget.
    actual_cost = 1.0 # Placeholder or derived from result?
    background_tasks.add_task(
        budget.record_transaction,
        user.user_id,
        actual_cost,
        {"trace_id": trace_id, "agent_id": agent_id}
    )

    # 8. Audit End
    # Log completion via coreason-veritas.
    await auditor.log_event(
        "EXECUTION_COMPLETE",
        user_id=user.user_id,
        agent_id=agent_id,
        trace_id=trace_id
    )

    return RunResponse(result=result, trace_id=trace_id)
