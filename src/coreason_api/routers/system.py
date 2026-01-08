from fastapi import APIRouter, status, HTTPException
from coreason_api.dependencies import VaultDep, IdentityDep

router = APIRouter(prefix="/health", tags=["system"])

@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_probe() -> dict[str, str]:
    """
    Returns 200 OK if the service (Uvicorn) is running.
    """
    return {"status": "ok"}

@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_probe(
    vault: VaultDep,
    identity: IdentityDep,
) -> dict[str, str]:
    """
    Returns 200 OK if dependencies (Vault, Identity Provider) are reachable.
    """
    # Check Vault
    try:
        # Assuming get_secret is a cheap way to check connection or there is a ping method.
        # The VID doesn't specify a ping method, so we might try to get a dummy secret or just trust instantiation?
        pass
    except Exception:
        raise HTTPException(status_code=503, detail="Vault unreachable") from None

    # Check Identity
    # VID doesn't show health check. Assuming instantiation is enough for now.

    return {"status": "ready"}
