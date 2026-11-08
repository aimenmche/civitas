from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# Isolate API tests from the developer database.
TEST_DB = Path(tempfile.gettempdir()) / "civitas_pytest.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["CIVITAS_DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["CIVITAS_ENVIRONMENT"] = "test"
