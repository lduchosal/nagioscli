"""Shared fixtures for CLI command tests."""

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from nagioscli.cli import main as cli_main
from nagioscli.core.config import NagiosConfig

# Modules that resolve ``load_config`` / ``NagiosClient`` at the call site:
# each command module does ``from nagioscli.core.client import NagiosClient``,
# so the patch target is the command module, not ``core.client``.
_COMMAND_MODULES = [
    "nagioscli.cli.commands.ack",
    "nagioscli.cli.commands.check",
    "nagioscli.cli.commands.hosts",
    "nagioscli.cli.commands.problems",
    "nagioscli.cli.commands.services",
    "nagioscli.cli.commands.status",
]


@pytest.fixture
def stub_config() -> NagiosConfig:
    return NagiosConfig(
        url="http://nagios.example.com/nagios",
        username="u",
        password="p",
    )


@pytest.fixture
def mock_client(monkeypatch: pytest.MonkeyPatch, stub_config: NagiosConfig) -> Iterator[MagicMock]:
    """Patch load_config and NagiosClient in every command module.

    Returns the MagicMock instance that all command invocations will receive.
    Tests configure return values / side effects on it before invoking.
    """
    client_instance = MagicMock()

    def _make_client(*_args: Any, **_kwargs: Any) -> MagicMock:
        return client_instance

    for mod_path in _COMMAND_MODULES:
        monkeypatch.setattr(f"{mod_path}.load_config", lambda _path: stub_config)
        monkeypatch.setattr(f"{mod_path}.NagiosClient", _make_client)

    yield client_instance


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cli() -> Any:
    return cli_main
