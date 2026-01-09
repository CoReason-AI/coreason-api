# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from unittest.mock import MagicMock

import pytest
from coreason_api.main import hello_world, lifespan


def test_hello_world() -> None:
    assert hello_world() == "Hello World!"


@pytest.mark.anyio  # type: ignore[misc]
async def test_lifespan() -> None:
    app = MagicMock()
    async with lifespan(app):
        pass
