"""Tests for nagioscli.core.auth."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nagioscli.core import auth as auth_mod
from nagioscli.core.auth import (
    PASS_SEARCH_DIRS,
    _find_pass,
    _get_password_from_pass,
    get_credentials,
    load_cached_vouch_token,
)
from nagioscli.core.config import NagiosConfig
from nagioscli.core.exceptions import AuthenticationError


@pytest.fixture(autouse=True)
def pass_in_fixed_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """`pass` resolves to a fixed absolute path, whatever the host has."""
    monkeypatch.setattr(auth_mod, "_find_pass", lambda: "/usr/bin/pass")


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


class TestFindPass:
    """ken #1243 (Sonar S4036): `pass` comes from fixed dirs, never PATH."""

    @staticmethod
    def _exe(directory: Path, mode: int = 0o755) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        exe = directory / "pass"
        exe.write_text("#!/bin/sh\n")
        exe.chmod(mode)
        return exe

    def test_first_executable_in_order(self, tmp_path: Path) -> None:
        first = self._exe(tmp_path / "a")
        self._exe(tmp_path / "b")
        assert _find_pass([str(tmp_path / "missing"), str(first.parent), str(tmp_path / "b")]) == (
            str(first)
        )

    def test_skips_non_executable(self, tmp_path: Path) -> None:
        self._exe(tmp_path / "a", mode=0o644)
        ok = self._exe(tmp_path / "b")
        assert _find_pass([str(tmp_path / "a"), str(tmp_path / "b")]) == str(ok)

    def test_ignores_user_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = self._exe(tmp_path / "evil")
        monkeypatch.setenv("PATH", str(fake.parent))
        assert _find_pass([str(tmp_path / "empty")]) is None

    def test_default_dirs_are_absolute_system_dirs(self) -> None:
        assert all(d.startswith("/") for d in PASS_SEARCH_DIRS)
        assert "/usr/bin" in PASS_SEARCH_DIRS

    def test_runs_pass_by_absolute_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        run = MagicMock(return_value=MagicMock(returncode=0, stdout="pw\n", stderr=""))
        monkeypatch.setattr(subprocess, "run", run)
        _get_password_from_pass("nagios/u")
        assert run.call_args.args[0] == ["/usr/bin/pass", "nagios/u"]

    def test_not_found_in_fixed_dirs_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(auth_mod, "_find_pass", lambda: None)
        run = MagicMock()
        monkeypatch.setattr(subprocess, "run", run)
        with pytest.raises(AuthenticationError, match="'pass' command not found in /usr/bin"):
            _get_password_from_pass("nagios/u")
        run.assert_not_called()
