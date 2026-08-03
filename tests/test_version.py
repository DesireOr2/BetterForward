"""Tests for embedded application version."""

import importlib


def test_version_defaults_to_dev(monkeypatch):
    monkeypatch.delenv("BETTERFORWARD_VERSION", raising=False)
    monkeypatch.delenv("VERSION", raising=False)
    import src.version as version_module

    importlib.reload(version_module)
    assert version_module.VERSION == "dev"


def test_version_reads_betterforward_env(monkeypatch):
    monkeypatch.setenv("BETTERFORWARD_VERSION", "v1.2.3")
    monkeypatch.delenv("VERSION", raising=False)
    import src.version as version_module

    importlib.reload(version_module)
    assert version_module.VERSION == "v1.2.3"


def test_version_falls_back_to_version_env(monkeypatch):
    monkeypatch.delenv("BETTERFORWARD_VERSION", raising=False)
    monkeypatch.setenv("VERSION", "v9.9.9")
    import src.version as version_module

    importlib.reload(version_module)
    assert version_module.VERSION == "v9.9.9"
