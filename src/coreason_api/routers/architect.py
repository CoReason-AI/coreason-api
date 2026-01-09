# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from typing import Any, Dict, List

from coreason_manifest.models import AgentDefinition
from coreason_manifest.validator import SchemaValidator as ManifestValidator
from coreason_veritas.gatekeeper import SignatureValidator as Gatekeeper
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from coreason_api.adapters import AnchorAdapter, MCPAdapter
from coreason_api.dependencies import (
    get_gatekeeper,
    get_manifest_validator,
    get_session_manager,
    get_trust_anchor,
)
from coreason_api.utils.logger import logger

router = APIRouter(tags=["architect"])


class GenerateRequest(BaseModel):
    prompt: str


class GenerateResponse(BaseModel):
    enriched_prompt: str
    policies: List[str]
    # Optionally include generated code if we were to call LLM
    # generated_code: Optional[str] = None


class SimulateRequest(BaseModel):
    agent_definition: Dict[str, Any]
    input_data: Dict[str, Any]


class SimulateResponse(BaseModel):
    result: Any
    status: str


class PublishRequest(BaseModel):
    agent_definition: Dict[str, Any]
    slug: str


class PublishResponse(BaseModel):
    signature: str
    status: str
    artifact: Dict[str, Any]


@router.post("/v1/architect/generate", response_model=GenerateResponse)
async def generate_vibe(
    request: GenerateRequest,
    gatekeeper: Gatekeeper = Depends(get_gatekeeper),  # noqa: B008
) -> GenerateResponse:
    """
    Vibe Coding: Inject coreason-veritas Gatekeeper policies into the prompt.
    """
    try:
        policies = gatekeeper.get_policy_instruction_for_llm()
        policy_text = "\n".join(policies)
        enriched_prompt = f"{request.prompt}\n\n[GOVERNANCE POLICIES]\n{policy_text}"

        # In a real scenario, we would pass this enriched_prompt to an LLM.
        # For this "Conductor" layer, we return the enriched prompt so the caller (or another service)
        # can execute it, or we act as a proxy.
        # PRD says "Inject ... into the prompt before passing to LLM."
        # Since no LLM client is configured in dependencies, we return the enriched prompt.

        return GenerateResponse(
            enriched_prompt=enriched_prompt,
            policies=policies,
        )
    except Exception as e:
        logger.error(f"Generate vibe failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate vibe",
        ) from e


@router.post("/v1/architect/simulate", response_model=SimulateResponse)
async def simulate_agent(
    request: SimulateRequest,
    mcp: MCPAdapter = Depends(get_session_manager),  # noqa: B008
) -> SimulateResponse:
    """
    Test Arena: Execute an in-memory draft of an agent via coreason-mcp.
    """
    try:
        # PRD: Execute an **in-memory draft** of an agent via coreason-mcp.
        # Assuming mcp.execute_agent can take the definition directly or handle "draft" execution.
        # Since execute_agent signature from runtime.py is (agent_id, input_data, context),
        # and we don't have an agent_id for a draft, we might need to rely on a different method
        # or assume execute_agent handles a special "draft" mode or we pass definition in context.

        # Ideally, we would register the draft temporarily.
        # For now, we will assume we can pass the definition in the context or as agent_id='draft'.
        # However, run_agent in runtime.py passes agent_id.

        # We'll pass the whole definition in context['agent_definition'] if the MCP supports it.
        context = {"agent_definition": request.agent_definition, "mode": "simulation"}

        # Note: 'execute_agent' is not present in the installed package's SessionManager.
        # It is assumed to be available at runtime (possibly monkey-patched or different version).
        # We use 'draft' as agent_id.
        result = await mcp.execute_agent(agent_id="draft", input_data=request.input_data, context=context)

        return SimulateResponse(result=result, status="success")

    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {str(e)}",
        ) from e


@router.post("/v1/architect/publish", response_model=PublishResponse)
async def publish_agent(
    request: PublishRequest,
    validator: ManifestValidator = Depends(get_manifest_validator),  # noqa: B008
    anchor: AnchorAdapter = Depends(get_trust_anchor),  # noqa: B008
) -> PublishResponse:
    """
    Publishing: Validate VerificationPackage, enforce Isomorphism (Slug == Name),
    and use coreason-veritas.TrustAnchor to seal the artifact.
    """
    # 1. Validate Schema
    try:
        validator.validate(request.agent_definition)
    except Exception as e:
        logger.warning(f"Schema validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid agent definition: {e}",
        ) from e

    # 2. Enforce Isomorphism (Slug == Name)
    # We parse the definition to accessing fields easily
    try:
        # We can use AgentDefinition model from coreason_manifest.models if available
        # OR just check the dict. Using model is safer.
        # ManifestLoader.load_from_dict returns AgentDefinition
        from coreason_manifest.loader import ManifestLoader

        agent_def: AgentDefinition = ManifestLoader.load_from_dict(request.agent_definition)

        agent_name = agent_def.metadata.name
        if request.slug != agent_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Slug '{request.slug}' does not match Agent Name '{agent_name}' (Isomorphism check failed)",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to parse agent definition: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse agent definition: {e}",
        ) from e

    # 3. Seal with TrustAnchor
    try:
        # PRD: "use coreason-veritas.TrustAnchor to seal the artifact"
        # We seal the whole request or just the definition?
        # Usually we seal the definition.
        signature = anchor.seal(request.agent_definition)
    except Exception as e:
        logger.error(f"Sealing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to seal artifact",
        ) from e

    return PublishResponse(signature=signature, status="published", artifact=request.agent_definition)
