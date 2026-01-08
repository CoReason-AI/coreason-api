# Copyright (c) 2025 CoReason, Inc.
#
# This software is proprietary and dual-licensed.
# Licensed under the Prosperity Public License 3.0 (the "License").
# A copy of the license is available at https://prosperitylicense.com/versions/3.0.0
# For details, see the LICENSE file.
# Commercial use beyond a 30-day trial requires a separate license.
#
# Source Code: https://github.com/CoReason-AI/coreason_api

from unittest.mock import patch

from coreason_api.utils.logger import setup_logger


def test_setup_logger_creates_directory() -> None:
    # Mock Path to verify mkdir is called
    with patch("coreason_api.utils.logger.Path") as MockPath:
        mock_path_obj = MockPath.return_value
        mock_path_obj.exists.return_value = False

        # Mock logger to avoid adding real sinks during test
        with patch("coreason_api.utils.logger.logger") as mock_logger:
            setup_logger()

            # Verify mkdir called
            mock_path_obj.mkdir.assert_called_with(parents=True, exist_ok=True)

            # Verify logger.remove and logger.add called
            mock_logger.remove.assert_called()
            assert mock_logger.add.call_count == 2


def test_setup_logger_directory_exists() -> None:
    with patch("coreason_api.utils.logger.Path") as MockPath:
        mock_path_obj = MockPath.return_value
        mock_path_obj.exists.return_value = True

        with patch("coreason_api.utils.logger.logger"):
            setup_logger()

            mock_path_obj.mkdir.assert_not_called()
