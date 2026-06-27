"""Shared pytest fixtures.

Tests run without USE_SECRET_MANAGER set, against env-var-only Settings.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Force every test to read fresh settings.

    `get_settings` is `lru_cache`d for runtime; in tests we want each case to
    start with a clean view of env vars after `monkeypatch.setenv`.
    """
    from app.core import config as _config

    _config.get_settings.cache_clear()
    yield
    _config.get_settings.cache_clear()


@pytest.fixture
def base_env(monkeypatch):
    """Minimal Settings env so Settings() can construct successfully."""
    monkeypatch.setenv("USE_SECRET_MANAGER", "false")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("DB_USER", "smfo")
    monkeypatch.setenv("DB_PASSWORD", "test-pw")
    monkeypatch.setenv("DB_NAME", "smfo")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    return monkeypatch
