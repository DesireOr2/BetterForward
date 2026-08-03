"""Tests for per-user sequential message queue behavior."""

import time
from threading import Event

from src.utils.message_queue import MessageQueueManager
from tests.helpers import make_message


def test_same_user_messages_processed_in_order():
    order = []
    started = Event()
    release = Event()

    def handler(message):
        if message.message_id == 1:
            started.set()
            release.wait(timeout=2)
        order.append(message.message_id)

    manager = MessageQueueManager(handler, num_workers=2)
    try:
        manager.put(make_message(message_id=1, user_id=7, chat_id=7))
        assert started.wait(timeout=2)

        manager.put(make_message(message_id=2, user_id=7, chat_id=7))
        # Give worker a chance to enqueue the second message behind the first.
        time.sleep(0.05)
        assert order == []

        release.set()
        deadline = time.time() + 2
        while time.time() < deadline and order != [1, 2]:
            time.sleep(0.01)

        assert order == [1, 2]
    finally:
        import src.config as config

        config.stop = True
        manager.stop()
        config.stop = False
