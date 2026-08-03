"""Multi-threaded message queue manager for BetterForward."""

import queue
import threading
from collections import defaultdict, deque
from typing import Callable

from telebot.types import Message
from telebot.util import antiflood

from src import config
from src.config import logger, _


class MessageQueueManager:
    """
    Manages message processing with multiple worker threads.

    Ensures messages from the same user/topic are processed sequentially.
    SQLite safety still depends on connection settings (WAL / busy_timeout);
    this queue only serializes per-user work.
    """

    def __init__(self, handler_func: Callable, num_workers: int = 5):
        self.handler_func = handler_func
        self.num_workers = num_workers
        self.main_queue = queue.Queue()
        self.user_queues = defaultdict(deque)
        self.processing_users = set()
        self.lock = threading.Lock()
        self.workers = []
        self._start_workers()

    def _start_workers(self):
        """Start worker threads."""
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker,
                name=f"MessageWorker-{i + 1}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        logger.info(_("Started {} message processing workers").format(self.num_workers))

    def _get_user_id(self, message: Message):
        """Extract user/topic identifier from message for queue grouping."""
        if message.chat.type == 'private':
            user = getattr(message, "from_user", None)
            if user is None:
                return f"private_unknown_{message.chat.id}"
            return user.id
        thread_id = getattr(message, "message_thread_id", None)
        return f"thread_{thread_id}"

    def _worker(self):
        """Worker thread that processes messages."""
        while not config.stop:
            try:
                message = self.main_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                user_id = self._get_user_id(message)
                with self.lock:
                    if user_id in self.processing_users:
                        self.user_queues[user_id].append(message)
                        continue
                    self.processing_users.add(user_id)

                self._process_user_messages(user_id, message)
            except Exception as e:
                logger.error(_("Worker error: {}").format(e))
                from traceback import print_exc
                print_exc()
            finally:
                self.main_queue.task_done()

    def _process_user_messages(self, user_id, first_message: Message):
        """Process all messages for a specific user sequentially."""
        try:
            try:
                antiflood(self.handler_func, first_message)
            except Exception as e:
                logger.error(_("Failed to process message for user {}: {}").format(user_id, e))
                from traceback import print_exc
                print_exc()

            while True:
                with self.lock:
                    if not self.user_queues[user_id]:
                        self.processing_users.discard(user_id)
                        if user_id in self.user_queues:
                            del self.user_queues[user_id]
                        break
                    next_message = self.user_queues[user_id].popleft()

                try:
                    antiflood(self.handler_func, next_message)
                except Exception as e:
                    logger.error(_("Failed to process message for user {}: {}").format(user_id, e))
                    from traceback import print_exc
                    print_exc()
        except Exception as e:
            logger.error(_("Failed to process message for user {}: {}").format(user_id, e))
            from traceback import print_exc
            print_exc()
            with self.lock:
                # Drain remaining queued messages so they are not orphaned.
                self.user_queues.pop(user_id, None)
                self.processing_users.discard(user_id)

    def put(self, message: Message):
        """Add a message to the processing queue."""
        self.main_queue.put(message)

    def stop(self):
        """Stop all workers and wait for them to finish."""
        logger.info(_("Stopping message queue manager..."))
        self.main_queue.join()
        for worker in self.workers:
            worker.join(timeout=5)
        logger.info(_("Message queue manager stopped"))

    def get_stats(self) -> dict:
        """Get current queue statistics."""
        with self.lock:
            return {
                "main_queue_size": self.main_queue.qsize(),
                "processing_users_count": len(self.processing_users),
                "user_queues_count": len(self.user_queues),
                "total_queued_messages": sum(len(q) for q in self.user_queues.values()),
                "workers_count": len(self.workers)
            }
