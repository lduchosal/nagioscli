"""Tests for nagioscli.core.auth."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nagioscli.core import auth as auth_mod
from nagioscli.core.auth import (
    _get_password_from_pass,
    get_credentials,
    load_cached_vouch_token,
)
from nagioscli.core.config import NagiosConfig
from nagioscli.core.exceptions import AuthenticationError


@pytest.fixture
def isolated_token_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirect TOKEN_CACHE_FILE to a tmp path for the duration of the test."""
    fake = tmp_path / "token"
    monkeypatch.setattr(auth_mod, "TOKEN_CACHE_FILE", fake)
    return fake


class TestLoadCachedVouchToken:
    def test_returns_none_when_no_file(self, isolated_token_cache: Path) -> None:
        assert load_cached_vouch_token() is None

    def test_returns_stripped_content(self, isolated_token_cache: Path) -> None:
        isolated_token_cache.write_text("  cookie-value\n")
        assert load_cached_vouch_token() == "cookie-value"


class TestGetCredentials:
    def test_vouch_cookie_in_config_returns_empty_password(
        self, isolated_token_cache: Path
    ) -> None:
        cfg = NagiosConfig(url="x", username="u", vouch_cookie="abc")
        assert get_credentials(cfg) == ("u", "")

    def test_cached_vouch_token_returns_empty_password(self, isolated_token_cache: Path) -> None:
        isolated_token_cache.write_text("tok")
        cfg = NagiosConfig(url="x", username="u")
        assert get_credentials(cfg) == ("u", "")

    def test_password_in_config(self, isolated_token_cache: Path) -> None:
        cfg = NagiosConfig(url="x", username="u", password="p")
        assert get_credentials(cfg) == ("u", "p")

    def test_no_password_raises(self, isolated_token_cache: Path) -> None:
        cfg = NagiosConfig(url="x", username="u")
        with pytest.raises(AuthenticationError, match="No password"):
            get_credentials(cfg)

    def test_pass_path_invokes_pass(
        self, isolated_token_cache: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        completed = MagicMock(returncode=0, stdout="secret\n", stderr="")
        monkeypatch.setattr(subprocess, "run", MagicMock(return_value=completed))
        cfg = NagiosConfig(url="x", username="u", pass_path="nagios/u")
        assert get_credentials(cfg) == ("u", "secret")


class TestGetPasswordFromPass:
    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        completed = MagicMock(returncode=0, stdout="pw\n", stderr="")
        monkeypatch.setattr(subprocess, "run", MagicMock(return_value=completed))
        assert _get_password_from_pass("nagios/u") == "pw"

    def test_nonzero_returncode_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        completed = MagicMock(returncode=1, stdout="", stderr="entry not found")
        monkeypatch.setattr(subprocess, "run", MagicMock(return_value=completed))
        with pytest.raises(AuthenticationError, match="entry not found"):
            _get_password_from_pass("missing")

    def test_empty_password_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        completed = MagicMock(returncode=0, stdout="\n", stderr="")
        monkeypatch.setattr(subprocess, "run", MagicMock(return_value=completed))
        with pytest.raises(AuthenticationError, match="Empty password"):
            _get_password_from_pass("nagios/u")

    def test_pass_not_installed_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_a: object, **_kw: object) -> None:
            raise FileNotFoundError

        monkeypatch.setattr(subprocess, "run", boom)
        with pytest.raises(AuthenticationError, match="pass.* not found"):
            _get_password_from_pass("nagios/u")

    def test_timeout_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_a: object, **_kw: object) -> None:
            raise subprocess.TimeoutExpired(cmd="pass", timeout=10)

        monkeypatch.setattr(subprocess, "run", boom)
        with pytest.raises(AuthenticationError, match="Timeout"):
            _get_password_from_pass("nagios/u")

    def test_unexpected_error_wrapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_a: object, **_kw: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(subprocess, "run", boom)
        with pytest.raises(AuthenticationError, match="disk full"):
            _get_password_from_pass("nagios/u")
