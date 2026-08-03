"""Pytest bootstrap for BetterForward.

src.config parses CLI args at import time, so argv must be set before imports.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.argv = [
    "pytest",
    "-token", "0000000000:TEST_TOKEN_FOR_UNIT_TESTS",
    "-group_id", "-1001234567890",
    "-language", "en_US",
]
