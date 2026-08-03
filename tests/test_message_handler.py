"""Core message forwarding and stale-topic compensation tests."""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from telebot.types import Message

from src.handlers.message_handler import MessageHandler
from src.utils.permissions import PermissionManager
from tests.helpers import (
    init_core_db,
    make_api_error,
    make_cache,
    make_message,
)


GROUP_ID = -1001234567890


@pytest.fixture
def handler_env(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_core_db(db_path)
    cache = make_cache({"setting_captcha": "disable"})
    bot = MagicMock()
    bot.token = "TEST_TOKEN"
    captcha = MagicMock()
    captcha.is_user_verified.return_value = True
    auto_response = MagicMock()
    auto_response.match_auto_response.return_value = None
    permission_manager = PermissionManager(db_path=db_path, cache=cache)

    handler = MessageHandler(
        bot=bot,
        group_id=GROUP_ID,
        db_path=db_path,
        cache=cache,
        captcha_manager=captcha,
        auto_response_manager=auto_response,
        permission_manager=permission_manager,
    )
    return handler, bot, cache, db_path


def _seed_topic(db_path: str, user_id: int, thread_id: int):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO topics (user_id, thread_id) VALUES (?, ?)",
            (user_id, thread_id),
        )
        conn.execute(
            "INSERT INTO messages (received_id, forwarded_id, topic_id, in_group) VALUES (?, ?, ?, ?)",
            (11, 22, thread_id, False),
        )
        conn.commit()


def test_is_topic_missing_error_detects_known_markers():
    assert MessageHandler._is_topic_missing_error(
        make_api_error("Bad Request: message thread not found")
    )
    assert MessageHandler._is_topic_missing_error(make_api_error("TOPIC_DELETED"))
    assert MessageHandler._is_topic_missing_error(make_api_error("Bad Request: topic not found"))
    assert not MessageHandler._is_topic_missing_error(make_api_error("Forbidden: bot was blocked"))


def test_forward_user_message_to_existing_topic(handler_env):
    handler, bot, cache, db_path = handler_env
    user_id = 101
    thread_id = 555
    _seed_topic(db_path, user_id, thread_id)
    cache.set(f"chat_{user_id}_threadid", thread_id)

    forwarded = MagicMock(spec=Message)
    forwarded.message_id = 9001
    bot.send_message.return_value = forwarded

    message = make_message(message_id=77, chat_id=user_id, user_id=user_id, text="hi")
    handler.handle_message(message)

    bot.send_message.assert_called()
    kwargs = bot.send_message.call_args.kwargs
    assert kwargs["chat_id"] == GROUP_ID
    assert kwargs["message_thread_id"] == thread_id
    assert kwargs["text"] == "hi"

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT received_id, forwarded_id, topic_id, in_group FROM messages WHERE received_id = ?",
            (77,),
        ).fetchone()
    assert row == (77, 9001, thread_id, 0)


def test_stale_topic_compensation_recreates_and_retries(handler_env):
    handler, bot, cache, db_path = handler_env
    user_id = 202
    stale_thread_id = 111
    new_thread_id = 222
    _seed_topic(db_path, user_id, stale_thread_id)
    cache.set(f"chat_{user_id}_threadid", stale_thread_id)
    cache.set(f"threadid_{stale_thread_id}_userid", user_id)

    forwarded = MagicMock(spec=Message)
    forwarded.message_id = 8002
    bot.send_message.side_effect = [
        make_api_error("Bad Request: message thread not found"),
        forwarded,
    ]
    pin_message = MagicMock(spec=Message)
    pin_message.message_id = 1

    message = make_message(message_id=88, chat_id=user_id, user_id=user_id, text="retry me")

    with patch(
        "src.handlers.message_handler.create_forum_topic",
        return_value={"message_thread_id": new_thread_id},
    ) as create_topic, patch(
        "src.handlers.message_handler.send_and_pin_user_info"
    ) as pin_info:
        handler.handle_message(message)

    create_topic.assert_called_once()
    pin_info.assert_called_once()
    assert bot.send_message.call_count == 2
    retry_kwargs = bot.send_message.call_args_list[1].kwargs
    assert retry_kwargs["message_thread_id"] == new_thread_id
    assert retry_kwargs["text"] == "retry me"
    assert retry_kwargs.get("reply_to_message_id") is None

    assert cache.get(f"chat_{user_id}_threadid") == new_thread_id
    assert cache.get(f"threadid_{stale_thread_id}_userid") is None

    with sqlite3.connect(db_path) as conn:
        topics = conn.execute("SELECT user_id, thread_id FROM topics").fetchall()
        stale_msgs = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE topic_id = ?",
            (stale_thread_id,),
        ).fetchone()[0]
        new_msg = conn.execute(
            "SELECT received_id, forwarded_id, topic_id FROM messages WHERE topic_id = ?",
            (new_thread_id,),
        ).fetchone()

    assert topics == [(user_id, new_thread_id)]
    assert stale_msgs == 0
    assert new_msg == (88, 8002, new_thread_id)
    bot.forward_message.assert_not_called()


def test_group_message_forwards_to_mapped_user(handler_env):
    handler, bot, cache, db_path = handler_env
    user_id = 303
    thread_id = 777
    _seed_topic(db_path, user_id, thread_id)

    forwarded = MagicMock(spec=Message)
    forwarded.message_id = 5001
    bot.send_message.return_value = forwarded

    message = make_message(
        message_id=66,
        chat_id=GROUP_ID,
        chat_type="supergroup",
        user_id=999,
        text="reply to user",
        message_thread_id=thread_id,
    )
    handler.handle_message(message)

    kwargs = bot.send_message.call_args.kwargs
    assert kwargs["chat_id"] == user_id
    assert kwargs["message_thread_id"] is None
    assert kwargs["text"] == "reply to user"

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT received_id, forwarded_id, topic_id, in_group FROM messages WHERE received_id = ?",
            (66,),
        ).fetchone()
    assert row == (66, 5001, thread_id, 1)


def test_denied_permission_blocks_forward(handler_env):
    handler, bot, cache, db_path = handler_env
    user_id = 404
    permission_manager = PermissionManager(db_path=db_path, cache=cache)
    permission_manager.set_user_override(user_id, "link", "deny")
    handler.permission_manager = permission_manager

    message = make_message(
        message_id=55,
        chat_id=user_id,
        user_id=user_id,
        text="visit https://spam.example",
    )
    handler.handle_message(message)

    bot.send_message.assert_called()
    # Restriction reply goes to the private chat, not the forum group.
    assert all(
        call.kwargs.get("chat_id") != GROUP_ID and call.args[:1] != (GROUP_ID,)
        for call in bot.send_message.call_args_list
    )
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert count == 0
