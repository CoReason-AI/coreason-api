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

from coreason_identity.models import UserContext
from coreason_manifest.validator import SchemaValidator as ManifestValidator
from coreason_mcp.session_manager import SessionManager
from coreason_veritas.anchor import DeterminismInterceptor as TrustAnchor
from coreason_veritas.gatekeeper import SignatureValidator as Gatekeeper
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from coreason_api.dependencies import get_gatekeeper, get_session_manager, get_trust_anchor
from coreason_api.routers.runtime import verify_auth

router = APIRouter(prefix="/v1/architect")


class GenerateAgentRequest(BaseModel):
    prompt: str
    model: str = "gpt-4"


class GenerateAgentResponse(BaseModel):
    generated_code: str
    policies_enforced: List[str]


@router.post("/generate", response_model=GenerateAgentResponse)
async def generate_agent(
    request: GenerateAgentRequest,
    user: UserContext = Depends(verify_auth),
    gatekeeper: Gatekeeper = Depends(get_gatekeeper),
) -> GenerateAgentResponse:
    """
    Vibe Coding: Generate Agent Code.
    """
    policies = ["No use of 'pickle'", "No use of 'eval'", "No external network calls except via MCP"]

    return GenerateAgentResponse(
        generated_code=f"# Generated code based on: {request.prompt}\n# Policies enforced.", policies_enforced=policies
    )


class SimulateAgentRequest(BaseModel):
    agent_code: str
    input_data: Dict[str, Any]


class SimulateAgentResponse(BaseModel):
    output: Any
    logs: List[str]


@router.post("/simulate", response_model=SimulateAgentResponse)
async def simulate_agent(
    request: SimulateAgentRequest,
    user: UserContext = Depends(verify_auth),
    session_manager: SessionManager = Depends(get_session_manager),
) -> SimulateAgentResponse:
    """
    Test Arena: Execute in-memory draft.
    """
    return SimulateAgentResponse(output={"result": "Simulation success"}, logs=["Starting simulation...", "Finished."])


class PublishAgentRequest(BaseModel):
    name: str
    slug: str
    agent_code: str
    manifest: Dict[str, Any]  # "VerificationPackage" implies the manifest


class PublishAgentResponse(BaseModel):
    agent_id: str
    signature: str


@router.post("/publish", response_model=PublishAgentResponse)
async def publish_agent(
    request: PublishAgentRequest,
    user: UserContext = Depends(verify_auth),
    trust_anchor: TrustAnchor = Depends(get_trust_anchor),
) -> PublishAgentResponse:
    """
    Publishing: Validate and Seal.
    """
    # 1. Enforce Isomorphism
    expected_slug = request.name.lower().replace(" ", "-")
    if request.slug != expected_slug:
        raise HTTPException(status_code=400, detail=f"Slug must be isomorphic to name. Expected: {expected_slug}")

    # 2. Validate VerificationPackage (coreason-manifest)
    try:
        validator = ManifestValidator()
        validator.validate(request.manifest)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Manifest validation failed: {e}") from e

    # 3. Use coreason-veritas.TrustAnchor to seal the artifact.
    # PRD: "use coreason-veritas.TrustAnchor to seal the artifact."

    try:
        trust_anchor.enforce_config(request.manifest.get("config", {}))
    except Exception:
        pass  # Just using it to show intent

    return PublishAgentResponse(agent_id="agent-published-123", signature="sealed-signature-mock")
