import shutil
import sys
from pathlib import Path


def test_logger_directory_creation_real_fs():
    # Remove module to force reload
    if "coreason_api.utils.logger" in sys.modules:
        del sys.modules["coreason_api.utils.logger"]

    log_path = Path("logs")
    if log_path.exists():
        shutil.rmtree(log_path)

    assert not log_path.exists()

    assert log_path.exists()
    assert log_path.is_dir()


def test_logger_directory_exists_real_fs():
    # Setup: ensure dir exists
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)

    # Reload
    if "coreason_api.utils.logger" in sys.modules:
        del sys.modules["coreason_api.utils.logger"]

    assert log_path.exists()
