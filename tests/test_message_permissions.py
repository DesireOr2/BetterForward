"""Tests for message permission classification."""

from types import SimpleNamespace

from src.utils.message_permissions import classify_message_permissions
from tests.helpers import make_message


def test_classify_plain_text_requires_no_permissions():
    message = make_message(text="hello world")
    assert classify_message_permissions(message) == ()


def test_classify_photo_and_raw_link():
    message = make_message(
        text=None,
        content_type="photo",
        caption="see https://example.com",
        photo=[SimpleNamespace(file_id="p1")],
    )
    assert classify_message_permissions(message) == ("photo", "link")


def test_classify_username_entity_and_raw_mention():
    entity = SimpleNamespace(type="mention")
    message = make_message(text="hi @alice", entities=[entity])
    assert "username" in classify_message_permissions(message)

    raw = make_message(text="ping @bob please")
    assert classify_message_permissions(raw) == ("username",)
