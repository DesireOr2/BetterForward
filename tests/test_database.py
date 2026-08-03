"""Tests for database helpers."""

import sqlite3

from src.database import Database
from tests.helpers import init_core_db


def test_set_setting_inserts_missing_key(tmp_path, monkeypatch):
    db_path = str(tmp_path / "storage.db")
    init_core_db(db_path)
    monkeypatch.chdir(tmp_path)
    # Avoid running migrate scanner against repo; construct with existing file.
    db = Database.__new__(Database)
    db.db_path = db_path
    import threading
    db.db_lock = threading.Lock()

    db.set_setting("brand_new_key", "value")
    assert db.get_setting("brand_new_key") == "value"
    db.set_setting("brand_new_key", "updated")
    assert db.get_setting("brand_new_key") == "updated"


def test_messages_indexes_migration(tmp_path):
    import importlib

    db_path = str(tmp_path / "test.db")
    init_core_db(db_path)
    module = importlib.import_module("db_migrate.20260803_messages_indexes")

    module.upgrade(db_path)
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    names = {row[0] for row in rows}
    assert "idx_messages_received" in names
    assert "idx_messages_forwarded" in names
