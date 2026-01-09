import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status
from pydantic import BaseModel

from coreason_api.dependencies import AuditorDep, BudgetDep, GatekeeperDep, IdentityDep, MCPDep

router = APIRouter(prefix="/v1", tags=["runtime"])


class RunAgentRequest(BaseModel):
    input_data: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None


@router.post("/run/{agent_id}")
async def run_agent(
    agent_id: str,
    request: RunAgentRequest,
    background_tasks: BackgroundTasks,
    identity: IdentityDep,
    budget: BudgetDep,
    auditor: AuditorDep,
    mcp: MCPDep,
    gatekeeper: GatekeeperDep,  # For Policy Check (optional explicit check mentioned in FR)
    authorization: str = Header(..., description="Bearer token"),
) -> Dict[str, Any]:
    """
    Production Runtime: Executes an agent following the Chain of Command.
    """

    # 2. Authentication
    # "Validate Bearer Token via coreason-identity"
    # Authorization header is typically "Bearer <token>"
    token = authorization.replace("Bearer ", "").strip()
    try:
        user_context = await identity.validate_token(token)
        # Assuming user_context has user_id, or we parse it
        # user_context might be a UserContext object or dict.
        # PRD Ref: from coreason_identity.models import UserContext
        # Let's assume it has .user_id or similar.
        user_id = getattr(user_context, "user_id", "unknown_user")
        if user_id == "unknown_user" and isinstance(user_context, dict):
            user_id = user_context.get("user_id", "unknown_user")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication failed: {e}") from e

    # 3. Policy Check (Optional explicit check)
    # "Verify agent access via coreason-veritas (optional explicit check)."
    # We can skip implementation detail if "optional", but let's log it.
    # gatekeeper.verify_asset(...) could be used if we had an asset signature.

    # 4. Budget Check
    # "Verify user quota via coreason-budget. Reject (402) if insufficient."
    cost_estimate = 0.01  # Placeholder cost or derived from request
    allowed = await budget.check_quota(user_id, cost_estimate)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient budget quota")

    # 5. Audit Start
    trace_id = str(uuid.uuid4())  # Ideally from context/middleware
    # We can get trace_id from logger context if available, or generate new event ID.
    await auditor.log_event("EXECUTION_START", {"agent_id": agent_id, "user_id": user_id, "trace_id": trace_id})

    # 6. Execution
    try:
        result = await mcp.execute_agent(agent_id, request.input_data, request.context)
    except Exception as e:
        await auditor.log_event("EXECUTION_ERROR", {"agent_id": agent_id, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}") from e

    # 7. Settlement
    # "Deduct cost via coreason-budget (fire-and-forget)."
    # Using BackgroundTasks for fire-and-forget
    # We need to await it in background.
    # record_transaction is async. FastAPI BackgroundTasks runs sync or async.
    background_tasks.add_task(budget.record_transaction, user_id, cost_estimate, {"agent_id": agent_id})

    # 8. Audit End
    # This should probably be done now, not background, to ensure audit log exists before response?
    # Or background? "Log completion".
    # I'll do it synchronously to be safe.
    await auditor.log_event("EXECUTION_END", {"agent_id": agent_id, "status": "success"})

    return {"result": result, "trace_id": trace_id}
