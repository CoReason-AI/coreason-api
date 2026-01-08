import sys
from unittest.mock import MagicMock

# Mocking external packages if they are not installed
external_packages = [
    "coreason_vault",
    "coreason_vault.main",
    "coreason_identity",
    "coreason_identity.manager",
    "coreason_identity.models",
    "coreason_budget",
    "coreason_budget.guard",
    "coreason_veritas",
    "coreason_veritas.auditor",
    "coreason_veritas.gatekeeper",
    "coreason_veritas.anchor",
    "coreason_mcp",
    "coreason_mcp.session_manager",
    "coreason_mcp.types",
    "coreason_manifest",
    "coreason_manifest.validator",
    "coreason_manifest.loader",
]

for package in external_packages:
    if package not in sys.modules:
        sys.modules[package] = MagicMock()
