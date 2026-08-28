"""Tests for auto-response matching."""

import pytz

from src.utils.auto_response import AutoResponseManager, looks_like_regex
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


def test_looks_like_regex_distinguishes_plain_keywords():
    assert looks_like_regex("hello") is False
    assert looks_like_regex(r"^hello\d+$") is True
    assert looks_like_regex("(") is False  # invalid pattern


def test_bad_regex_does_not_block_later_rules(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_core_db(db_path)
    manager = AutoResponseManager(db_path, pytz.UTC)
    manager.add_auto_response("(", "bad", is_regex=True, response_type="text")
    manager.add_auto_response(r"^ok$", "good", is_regex=True, response_type="text")
    assert manager.match_auto_response("ok") == {"response": "good", "type": "text"}
