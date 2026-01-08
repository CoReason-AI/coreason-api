from typing import Any, Dict

# We assume types for the mocked packages
from coreason_identity.models import UserContext
from coreason_mcp.types import SessionContext
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from coreason_api.dependencies import AuditorDep, BudgetDep, IdentityDep, SessionDep

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
        raise HTTPException(status_code=401, detail=f"Authentication failed: {e}") from e

    # 3. Policy Check (Optional Explicit)
    # PRD says: "Verify agent access via coreason-veritas (optional explicit check)."

    # 4. Budget Check
    # PRD: Verify user quota via coreason-budget. Reject (402) if insufficient.
    # VID: allowed = await budget.check_quota(user_id, cost_estimate)
    # We need a cost estimate. Hardcode or derive?
    estimated_cost = 1.0  # Placeholder

    try:
        if not await budget.check_quota(user.user_id, estimated_cost):
            raise HTTPException(status_code=402, detail="Insufficient funds")
    except Exception as e:
        # If check_quota raises, handle it
        if isinstance(e, HTTPException):
            raise e
        # If external error
        raise HTTPException(status_code=500, detail=f"Budget check failed: {e}") from e

    # 5. Audit Start
    # VID: await auditor.log_event("EXECUTION_START", ...)
    await auditor.log_event(
        "EXECUTION_START",
        user_id=user.user_id,
        agent_id=agent_id,
        trace_id=trace_id,
        input_hash=str(hash(str(request_body.input_data))),  # Simple hash
    )

    # 6. Execution
    # VID: result = await mcp.execute_agent(agent_id, input_data, context)
    # We need to construct SessionContext or pass dict? VID says `SessionContext` type exists.
    # But `execute_agent` usage shows `context` passed as arg.
    # Let's pass the dictionary.

    # We should probably mix request context with user info.
    execution_context = SessionContext(user_id=user.user_id, trace_id=trace_id, **request_body.context)

    try:
        result = await session_manager.execute_agent(agent_id, request_body.input_data, execution_context)
    except Exception as e:
        # Audit failure?
        await auditor.log_event(
            "EXECUTION_FAILED", user_id=user.user_id, agent_id=agent_id, trace_id=trace_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Execution failed: {e}") from e

    # 7. Settlement
    # PRD: Deduct cost via coreason-budget (fire-and-forget).
    # We use BackgroundTasks for fire-and-forget.
    actual_cost = 1.0  # Placeholder or derived from result?
    background_tasks.add_task(
        budget.record_transaction, user.user_id, actual_cost, {"trace_id": trace_id, "agent_id": agent_id}
    )

    # 8. Audit End
    # Log completion via coreason-veritas.
    await auditor.log_event("EXECUTION_COMPLETE", user_id=user.user_id, agent_id=agent_id, trace_id=trace_id)

    return RunResponse(result=result, trace_id=trace_id)
