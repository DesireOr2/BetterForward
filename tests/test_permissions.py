"""Tests for permission resolution."""

from src.utils.permissions import PermissionManager
from tests.helpers import init_core_db, make_cache


def test_permission_resolve_default_allow_override_deny(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_core_db(db_path)
    cache = make_cache()
    manager = PermissionManager(db_path=db_path, cache=cache)

    assert manager.resolve_permission(1, "photo") is True

    manager.set_user_override(1, "photo", "deny")
    assert manager.resolve_permission(1, "photo") is False

    manager.set_user_override(1, "photo", "allow")
    manager.set_global_default("photo", False)
    assert manager.resolve_permission(1, "photo") is True

    manager.clear_user_override(1, "photo")
    assert manager.resolve_permission(1, "photo") is False
