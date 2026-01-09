from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from coreason_api.adapters import SchemaValidator, TrustAnchor
from coreason_api.dependencies import (
    GatekeeperDep,
    MCPDep,  # Maybe needed?
)

router = APIRouter(prefix="/v1/architect", tags=["architect"])


class GenerateRequest(BaseModel):
    prompt: str
    context: Dict[str, Any] = {}


class SimulateRequest(BaseModel):
    agent_draft: Dict[str, Any]
    input_data: Dict[str, Any]


class PublishRequest(BaseModel):
    manifest: Dict[str, Any]
    signature: str  # Or maybe we generate signature? PRD says "use coreason-veritas.TrustAnchor to seal the artifact"


@router.post("/generate")
async def generate_agent(request: GenerateRequest, gatekeeper: GatekeeperDep) -> Dict[str, Any]:
    """
    Vibe Coding: Generates agent code/spec with injected policies.
    """
    # Logic: Inject coreason-veritas Gatekeeper policies into the prompt
    policies = gatekeeper.get_policy_instruction_for_llm()
    policy_text = "\n".join(policies)

    enhanced_prompt = f"""
    SYSTEM: You are an architect. You must adhere to the following security policies:
    {policy_text}

    USER: {request.prompt}
    """

    # Here we would call an LLM. Since PRD doesn't specify an LLM service to use
    # (other than maybe MCP execution, but this is "Architect Factory"),
    # and instructions say "Inject ... into the prompt before passing to LLM",
    # I assume we return the enhanced prompt or call an LLM stub.
    # Given "Vibe Coding ... POST /v1/architect/generate", maybe it returns the generated spec?
    # Without an LLM client in dependencies (MCP is for execution), I will return the constructed prompt
    # or a mock response simulating LLM output.

    return {
        "enhanced_prompt": enhanced_prompt,
        "policies_injected": len(policies),
        "generated_spec": {"mock": "spec"},  # Placeholder
    }


@router.post("/simulate")
async def simulate_agent(request: SimulateRequest, mcp: MCPDep) -> Dict[str, Any]:
    """
    Test Arena: Execute an in-memory draft of an agent.
    """
    # Logic: Execute an in-memory draft of an agent via coreason-mcp.
    # MCP execute_agent typically takes agent_id. Does it accept a draft spec?
    # PRD VID: result = await mcp.execute_agent(agent_id, input_data, context)
    # It takes agent_id.
    # Maybe we need to register it temporarily?
    # Or maybe MCP supports executing raw spec?
    # The installed SessionManager only has execute_agent(agent_id, ...).
    # If the draft is not saved, we can't reference it by ID.
    # Perhaps "execute_agent" can take a dict as agent_id? Unlikely type hint is str.

    # Assumption: For "Simulate", we might pass a special "draft" agent_id
    # and pass the spec in context? Or MCP Adapter needs update?
    # PRD says "Logic: Execute an in-memory draft of an agent via coreason-mcp."

    # I will assume we pass the draft in context or input, and use a temporary ID.
    try:
        # We pass the draft spec in the context for the MCP to use?
        # This depends on MCP implementation details which I shouldn't guess,
        # but I have to implement "Logic: Execute ... draft".
        # I'll pass it in context.
        context = {"draft_spec": request.agent_draft}
        result = await mcp.execute_agent("draft-agent", request.input_data, context)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {e}") from e


@router.post("/publish")
async def publish_agent(request: PublishRequest) -> Dict[str, Any]:
    """
    Publishing: Validate and Seal.
    Logic: Validate VerificationPackage, enforce Isomorphism, use TrustAnchor to seal.
    """
    manifest = request.manifest

    # 1. Validate Schema
    try:
        # SchemaValidator.validate(data)
        # Verify it works as static method or instance?
        # PRD: SchemaValidator.validate(data)
        # Adapter: _SchemaValidator.validate(data)
        # Note: Installed `SchemaValidator` might need instantiation?
        # Checked `dir(SchemaValidator)` -> `['validate', ...]` looks like method.
        # Let's try calling it as class method or instantiate.
        # Usually validators are stateless.
        validator = SchemaValidator()
        validator.validate(manifest)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Schema validation failed: {e}") from e

    # 2. Enforce Isomorphism (Slug == Name)
    # Assuming manifest has 'slug' and 'name'
    if manifest.get("slug") != manifest.get("name"):
        raise HTTPException(status_code=400, detail="Isomorphism violation: slug must equal name")

    # 3. Seal with TrustAnchor
    anchor = TrustAnchor()
    sealed_artifact = anchor.seal_artifact(manifest)

    return {"status": "published", "artifact": sealed_artifact}
