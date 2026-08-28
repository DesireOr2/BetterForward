"""Tests for admin menu/callback authorization."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.handlers.admin_handler import AdminHandler
from src.handlers.callback_handler import CallbackHandler
from src.handlers.command_handler import CommandHandler
from tests.helpers import make_cache, make_message


GROUP_ID = -1001234567890


def _admin_handler(bot=None, cache=None):
    bot = bot or MagicMock()
    cache = cache or make_cache()
    return AdminHandler(
        bot=bot,
        group_id=GROUP_ID,
        db_path=":memory:",
        cache=cache,
        database=MagicMock(),
        auto_response_manager=MagicMock(),
    )


def test_menu_hidden_for_non_admin():
    bot = MagicMock()
    bot.get_chat_member.return_value = SimpleNamespace(status="member")
    handler = _admin_handler(bot=bot)
    message = make_message(chat_id=GROUP_ID, chat_type="supergroup", message_thread_id=None, user_id=9)
    handler.menu(message)
    bot.send_message.assert_not_called()


def test_menu_shown_for_admin():
    bot = MagicMock()
    bot.get_chat_member.return_value = SimpleNamespace(status="administrator")
    handler = _admin_handler(bot=bot)
    message = make_message(chat_id=GROUP_ID, chat_type="supergroup", message_thread_id=None, user_id=1)
    handler.menu(message)
    bot.send_message.assert_called_once()


def test_callback_rejects_non_admin_before_action():
    bot = MagicMock()
    bot.get_chat_member.return_value = SimpleNamespace(status="member")
    admin = _admin_handler(bot=bot)
    command = MagicMock(spec=CommandHandler)
    captcha = MagicMock()
    handler = CallbackHandler(bot, GROUP_ID, admin, command, captcha, db_path=":memory:")

    call = SimpleNamespace(
        id="cb1",
        data='{"action":"show_version"}',
        from_user=SimpleNamespace(id=9),
        message=SimpleNamespace(chat=SimpleNamespace(id=GROUP_ID), message_id=1),
    )
    handler.handle_callback_query(call)
    bot.answer_callback_query.assert_called_once()
    assert bot.answer_callback_query.call_args.kwargs.get("show_alert") is True
    bot.send_message.assert_not_called()


def test_verify_button_rejects_other_user():
    bot = MagicMock()
    captcha = MagicMock()
    handler = CallbackHandler(bot, GROUP_ID, MagicMock(), MagicMock(), captcha, db_path=":memory:")
    call = SimpleNamespace(
        id="cb2",
        data='{"action":"verify_button","user_id":100}',
        from_user=SimpleNamespace(id=200),
        message=SimpleNamespace(chat=SimpleNamespace(id=1), message_id=2),
    )
    handler.handle_callback_query(call)
    captcha.set_user_verified.assert_not_called()
    assert bot.answer_callback_query.call_args.kwargs.get("show_alert") is True


def test_next_step_ignores_non_operator():
    bot = MagicMock()
    bot.get_chat_member.return_value = SimpleNamespace(status="administrator")
    cache = make_cache()
    handler = _admin_handler(bot=bot, cache=cache)
    handler.set_operator(1)
    other = make_message(chat_id=GROUP_ID, chat_type="supergroup", message_thread_id=None, user_id=2, text="hijack")
    assert handler._accept_admin_step(other, handler.add_auto_response_type) is False
    bot.register_next_step_handler.assert_called_once()
