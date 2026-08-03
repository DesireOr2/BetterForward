"""Tests for auto-response matching."""

import pytz

from src.utils.auto_response import AutoResponseManager
from tests.helpers import init_core_db


def test_exact_and_regex_auto_response(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_core_db(db_path)
    manager = AutoResponseManager(db_path, pytz.UTC)

    manager.add_auto_response("hello", "world", is_regex=False, response_type="text")
    manager.add_auto_response(r"^order\s+\d+$", "queued", is_regex=True, response_type="text")

    assert manager.match_auto_response("hello") == {"response": "world", "type": "text"}
    assert manager.match_auto_response("order 42") == {"response": "queued", "type": "text"}
    assert manager.match_auto_response("nope") is None
    assert manager.match_auto_response(None) is None
