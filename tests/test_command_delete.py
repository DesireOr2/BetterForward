"""Tests for multi-chunk message deletion."""

import sqlite3
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.handlers.command_handler import CommandHandler
from src.utils.captcha import CaptchaManager
from tests.helpers import init_core_db, make_cache, make_message


GROUP_ID = -1001234567890


def test_delete_removes_all_forwarded_chunks(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_core_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO topics (user_id, thread_id) VALUES (?, ?)", (101, 55))
        conn.execute(
            "INSERT INTO messages (received_id, forwarded_id, topic_id, in_group) VALUES (?, ?, ?, ?)",
            (10, 201, 55, 1),
        )
        conn.execute(
            "INSERT INTO messages (received_id, forwarded_id, topic_id, in_group) VALUES (?, ?, ?, ?)",
            (10, 202, 55, 1),
        )
        conn.commit()

    bot = MagicMock()
    bot.get_me.return_value = SimpleNamespace(id=-1, username="bot")
    cache = make_cache()
    captcha = CaptchaManager(bot, cache, GROUP_ID)
    handler = CommandHandler(bot, GROUP_ID, db_path, cache, None, captcha)

    reply = make_message(message_id=10, chat_id=GROUP_ID, chat_type="supergroup",
                         message_thread_id=55, user_id=1)
    reply.id = reply.message_id
    message = make_message(message_id=11, chat_id=GROUP_ID, chat_type="supergroup",
                           message_thread_id=55, user_id=1, text="/delete")
    message.reply_to_message = reply
    message.id = message.message_id

    handler.delete_message(message)

    deleted_ids = sorted(call.kwargs["message_id"] for call in bot.delete_message.call_args_list
                         if call.kwargs.get("chat_id") == 101)
    assert deleted_ids == [201, 202]
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM messages WHERE received_id = 10").fetchone()[0]
    assert count == 0


def test_ban_clears_verification_cache(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_core_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO topics (user_id, thread_id) VALUES (?, ?)", (303, 77))
        conn.execute("INSERT INTO verified_users (user_id) VALUES (?)", (303,))
        conn.commit()

    bot = MagicMock()
    bot.get_chat_member.return_value = SimpleNamespace(status="administrator")
    bot.token = "t"
    cache = make_cache({"verified_303": True})
    captcha = CaptchaManager(bot, cache, GROUP_ID)
    handler = CommandHandler(bot, GROUP_ID, db_path, cache, None, captcha)

    message = make_message(chat_id=GROUP_ID, chat_type="supergroup", message_thread_id=77, user_id=1)
    with MagicMock() as _:
        from unittest.mock import patch
        with patch("src.handlers.command_handler.close_forum_topic"):
            handler.ban_user(message)

    assert cache.get("verified_303") is None
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT 1 FROM verified_users WHERE user_id = 303").fetchone() is None
