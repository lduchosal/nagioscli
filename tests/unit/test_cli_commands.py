"""End-to-end CLI tests via Click's CliRunner.

Each command module is patched so ``load_config`` returns a stub config
and ``NagiosClient`` returns a shared MagicMock (see ``conftest.py``).
Tests then configure the mock's return values and assert on output +
exit codes.
"""

import json
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from nagioscli.core.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NagiosAPIError,
    NotFoundError,
)
from nagioscli.core.models import Host, Service

# ---------------------------------------------------------------- helpers ----


def _svc(host: str = "web01", desc: str = "HTTP", status: int = 2, **extra: object) -> Service:
    return Service(
        host_name=host, description=desc, status=status, plugin_output="OK", **extra
    )


def _host(name: str = "web01", status: int = 2, **extra: object) -> Host:
    return Host(name=name, address="10.0.0.1", status=status, plugin_output="UP", **extra)


# ----------------------------------------------------------------- problems --


class TestProblems:
    def test_text_output_lists_problems(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_problems.return_value = [
            _svc(status=16, desc="HTTP"),
            _svc(status=4, host="db01", desc="MySQL"),
        ]
        result = runner.invoke(cli, ["problems"])
        assert result.exit_code == 0
        assert "CRITICAL" in result.output
        assert "WARNING" in result.output
        assert "Total: 2 problem(s)" in result.output

    def test_text_output_empty(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_problems.return_value = []
        result = runner.invoke(cli, ["problems"])
        assert result.exit_code == 0
        assert "No problems found" in result.output

    def test_json_output(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_problems.return_value = [_svc(status=16)]
        result = runner.invoke(cli, ["problems", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload == [
            {"host": "web01", "service": "HTTP", "status": 16, "status_text": "CRITICAL"}
        ]

    def test_quiet_exits_0_when_no_problems(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_problems.return_value = []
        result = runner.invoke(cli, ["problems", "--quiet"])
        assert result.exit_code == 0

    def test_quiet_exits_1_when_problems(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_problems.return_value = [_svc(status=16)]
        result = runner.invoke(cli, ["problems", "--quiet"])
        assert result.exit_code == 1

    def test_api_error_maps_to_exit_4(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_problems.side_effect = NagiosAPIError("boom")
        result = runner.invoke(cli, ["problems"])
        assert result.exit_code == 4
        assert "API error" in result.output


# ------------------------------------------------------------------- status --


class TestStatus:
    def test_service_text(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_service_status.return_value = _svc(
            status=16, problem_acknowledged=True, scheduled_downtime=True
        )
        result = runner.invoke(cli, ["status", "service", "web01", "HTTP"])
        assert result.exit_code == 0
        assert "Host: web01" in result.output
        assert "Status: CRITICAL" in result.output
        assert "Acknowledged: Yes" in result.output
        assert "Downtime: Yes" in result.output

    def test_service_json(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_service_status.return_value = _svc(status=4)
        result = runner.invoke(cli, ["status", "service", "web01", "HTTP", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["status_text"] == "WARNING"

    def test_service_quiet(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_service_status.return_value = _svc(status=2)
        result = runner.invoke(cli, ["status", "service", "web01", "HTTP", "--quiet"])
        assert result.exit_code == 0
        assert result.output.strip() == "OK"

    def test_service_not_found_maps_to_exit_5(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_service_status.side_effect = NotFoundError("nope")
        result = runner.invoke(cli, ["status", "service", "web01", "HTTP"])
        assert result.exit_code == 5

    def test_host_text(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_host_status.return_value = _host(
            status=4, problem_acknowledged=True, scheduled_downtime=True
        )
        result = runner.invoke(cli, ["status", "host", "web01"])
        assert result.exit_code == 0
        assert "Status: DOWN" in result.output
        assert "Acknowledged: Yes" in result.output
        assert "Downtime: Yes" in result.output

    def test_host_json(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_host_status.return_value = _host(status=2)
        result = runner.invoke(cli, ["status", "host", "web01", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["status_text"] == "UP"

    def test_host_quiet(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_host_status.return_value = _host(status=8)
        result = runner.invoke(cli, ["status", "host", "web01", "--quiet"])
        assert result.exit_code == 0
        assert result.output.strip() == "UNREACHABLE"

    def test_host_auth_error_maps_to_exit_3(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_host_status.side_effect = AuthenticationError("bad")
        result = runner.invoke(cli, ["status", "host", "web01"])
        assert result.exit_code == 3


# -------------------------------------------------------------------- check --


class TestCheck:
    def test_check_service_success(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.force_service_check.return_value = True
        result = runner.invoke(cli, ["check", "web01", "HTTP"])
        assert result.exit_code == 0
        assert "Force check submitted" in result.output

    def test_check_service_failure(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.force_service_check.return_value = False
        result = runner.invoke(cli, ["check", "web01", "HTTP"])
        assert result.exit_code == 0
        assert "Failed to submit" in result.output

    def test_check_host_success(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.force_host_check.return_value = True
        result = runner.invoke(cli, ["check-host", "web01"])
        assert result.exit_code == 0
        assert "Force check submitted for host web01" in result.output

    def test_check_host_failure(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.force_host_check.return_value = False
        result = runner.invoke(cli, ["check-host", "web01"])
        assert result.exit_code == 0
        assert "Failed to submit" in result.output

    def test_check_host_services_success(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.force_host_services_check.return_value = True
        result = runner.invoke(cli, ["check-host-services", "web01"])
        assert result.exit_code == 0
        assert "Force check of all services submitted" in result.output

    def test_check_host_services_failure(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.force_host_services_check.return_value = False
        result = runner.invoke(cli, ["check-host-services", "web01"])
        assert result.exit_code == 0
        assert "Failed to submit" in result.output

    def test_check_api_error(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.force_service_check.side_effect = NagiosAPIError("nope")
        result = runner.invoke(cli, ["check", "web01", "HTTP"])
        assert result.exit_code == 4


# ---------------------------------------------------------------------- ack --


class TestAck:
    def test_ack_service_success(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.acknowledge_service.return_value = True
        result = runner.invoke(cli, ["ack", "web01", "HTTP", "working on it"])
        assert result.exit_code == 0
        assert "Acknowledged web01/HTTP" in result.output

    def test_ack_service_failure(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.acknowledge_service.return_value = False
        result = runner.invoke(cli, ["ack", "web01", "HTTP", "x"])
        assert "Failed" in result.output

    def test_ack_host_success(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.acknowledge_host.return_value = True
        result = runner.invoke(cli, ["ack-host", "web01", "rebooting"])
        assert result.exit_code == 0
        assert "Acknowledged host web01" in result.output

    def test_ack_host_failure(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.acknowledge_host.return_value = False
        result = runner.invoke(cli, ["ack-host", "web01", "x"])
        assert "Failed" in result.output

    def test_ack_propagates_unknown_error_as_exit_1(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.acknowledge_service.side_effect = RuntimeError("kaboom")
        result = runner.invoke(cli, ["ack", "web01", "HTTP", "c"])
        assert result.exit_code == 1
        assert "Error: kaboom" in result.output


# ------------------------------------------------------------------- hosts ---


class TestHosts:
    def test_text(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_all_hosts.return_value = [_host("a", 2), _host("b", 4)]
        result = runner.invoke(cli, ["hosts"])
        assert result.exit_code == 0
        assert "UP" in result.output
        assert "DOWN" in result.output
        assert "Total: 2 host(s)" in result.output

    def test_json(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_all_hosts.return_value = [_host("a", 2)]
        result = runner.invoke(cli, ["hosts", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload == [{"host": "a", "status": 2, "status_text": "UP"}]

    def test_quiet(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_all_hosts.return_value = [_host("a"), _host("b")]
        result = runner.invoke(cli, ["hosts", "--quiet"])
        assert result.exit_code == 0
        assert result.output.split() == ["a", "b"]

    def test_config_error(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_all_hosts.side_effect = ConfigurationError("missing")
        result = runner.invoke(cli, ["hosts"])
        assert result.exit_code == 2


# ----------------------------------------------------------------- services --


class TestServices:
    def test_text(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_host_services.return_value = [_svc(desc="HTTP", status=2)]
        result = runner.invoke(cli, ["services", "web01"])
        assert result.exit_code == 0
        assert "OK" in result.output
        assert "HTTP" in result.output
        assert "Total: 1 service(s)" in result.output

    def test_json(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_host_services.return_value = [_svc(desc="HTTP", status=4)]
        result = runner.invoke(cli, ["services", "web01", "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload[0]["status_text"] == "WARNING"

    def test_quiet(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_host_services.return_value = [_svc(desc="HTTP"), _svc(desc="SSH")]
        result = runner.invoke(cli, ["services", "web01", "--quiet"])
        assert result.exit_code == 0
        assert result.output.split() == ["HTTP", "SSH"]


# ------------------------------------------------------------------- login ---


class TestLoginLogout:
    def test_login_writes_token(
        self, runner: CliRunner, cli: object, tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from nagioscli.cli.commands import login as login_mod
        from nagioscli.core import auth as auth_mod

        fake = tmp_path / ".nagioscli_token"  # type: ignore[operator]
        monkeypatch.setattr(login_mod, "TOKEN_CACHE_FILE", fake)
        monkeypatch.setattr(auth_mod, "TOKEN_CACHE_FILE", fake)

        result = runner.invoke(cli, ["login"], input="my-secret-cookie\n")
        assert result.exit_code == 0
        assert fake.read_text() == "my-secret-cookie"
        assert "Token saved" in result.output

    def test_login_with_empty_token(
        self, runner: CliRunner, cli: object, tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from nagioscli.cli.commands import login as login_mod

        fake = tmp_path / ".nagioscli_token"  # type: ignore[operator]
        monkeypatch.setattr(login_mod, "TOKEN_CACHE_FILE", fake)

        # click.prompt with no default rejects empty input, so it re-prompts;
        # feed a single whitespace to bypass and verify the strip + save path.
        result = runner.invoke(cli, ["login"], input=" \n")
        # After strip the token is empty: save still writes "" (empty file).
        # Either way the command exits cleanly.
        assert result.exit_code == 0

    def test_logout_when_token_exists(
        self, runner: CliRunner, cli: object, tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from nagioscli.cli.commands import login as login_mod

        fake = tmp_path / ".nagioscli_token"  # type: ignore[operator]
        fake.write_text("xyz")
        monkeypatch.setattr(login_mod, "TOKEN_CACHE_FILE", fake)

        result = runner.invoke(cli, ["logout"])
        assert result.exit_code == 0
        assert not fake.exists()
        assert "Logged out" in result.output

    def test_logout_when_no_token(
        self, runner: CliRunner, cli: object, tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from nagioscli.cli.commands import login as login_mod

        fake = tmp_path / ".nagioscli_token"  # type: ignore[operator]
        monkeypatch.setattr(login_mod, "TOKEN_CACHE_FILE", fake)

        result = runner.invoke(cli, ["logout"])
        assert result.exit_code == 0
        assert "No saved token" in result.output


# ----------------------------------------------------------------- verbose ---


class TestVerbose:
    def test_verbose_emits_debug_to_stderr(
        self, runner: CliRunner, cli: object, mock_client: MagicMock
    ) -> None:
        mock_client.get_problems.return_value = []
        # mix_stderr is the default in CliRunner — stderr lands in result.output.
        result = runner.invoke(cli, ["problems", "-v"])
        assert result.exit_code == 0
        assert "DEBUG" in result.output
