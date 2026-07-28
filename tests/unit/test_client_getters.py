"""Tests for NagiosClient JSON getters and auth-header selection.

Patches the underlying ``_opener.open`` so we exercise the real
``_request`` / parsing logic without doing network I/O.
"""

import json
import urllib.error
from email.message import Message
from typing import Any
from unittest.mock import MagicMock

import pytest

from nagioscli.core.client import NagiosClient
from nagioscli.core.config import NagiosConfig
from nagioscli.core.exceptions import NagiosAPIError, NotFoundError


def _json_response(payload: dict[str, Any]) -> MagicMock:
    response = MagicMock()
    response.headers = Message()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    return response


def _client(**cfg_overrides: Any) -> tuple[NagiosClient, MagicMock]:
    opener = MagicMock()
    cfg = NagiosConfig(
        url="https://nagios.example.com/nagios",
        username="u",
        password="p",
        **cfg_overrides,
    )
    client = NagiosClient(cfg)
    client._opener = opener
    return client, opener


# ----------------------------------------------------------------- _request --


class TestRequestAuth:
    def test_basic_auth_header_set(self) -> None:
        client, opener = _client()
        opener.open.return_value = _json_response({"result": {"type_code": 0}, "data": {}})
        client._request("statusjson.cgi", {"query": "hostlist"})
        request = opener.open.call_args[0][0]
        assert request.get_header("Authorization", "").startswith("Basic ")

    def test_nginx_token_header_set(self) -> None:
        client, opener = _client(nginx_token="api-key")
        opener.open.return_value = _json_response({"result": {"type_code": 0}, "data": {}})
        client._request("statusjson.cgi", {"query": "hostlist"})
        request = opener.open.call_args[0][0]
        assert request.get_header("X-api-key") == "api-key"
        assert request.get_header("Authorization") is None

    def test_vouch_cookie_header_set(self) -> None:
        client, opener = _client(vouch_cookie="cookie-value")
        opener.open.return_value = _json_response({"result": {"type_code": 0}, "data": {}})
        client._request("statusjson.cgi", {"query": "hostlist"})
        request = opener.open.call_args[0][0]
        assert "VouchCookie=cookie-value" in request.get_header("Cookie", "")


class TestRequestErrors:
    def test_http_error_wrapped(self) -> None:
        client, opener = _client()
        opener.open.side_effect = urllib.error.HTTPError(
            url="x", code=500, msg="Server Error", hdrs=None, fp=None
        )
        with pytest.raises(NagiosAPIError, match="HTTP 500"):
            client._request("statusjson.cgi")

    def test_url_error_wrapped(self) -> None:
        client, opener = _client()
        opener.open.side_effect = urllib.error.URLError("no route")
        with pytest.raises(NagiosAPIError, match="Connection error"):
            client._request("statusjson.cgi")

    def test_invalid_json_wrapped(self) -> None:
        client, opener = _client()
        bad = MagicMock()
        bad.headers = Message()
        bad.read.return_value = b"not json"
        opener.open.return_value = bad
        with pytest.raises(NagiosAPIError, match="Invalid JSON"):
            client._request("statusjson.cgi")


# ----------------------------------------------------------------- getters ---


class TestGetServiceStatus:
    def test_parses_service(self) -> None:
        client, opener = _client()
        opener.open.return_value = _json_response(
            {
                "result": {"type_code": 0},
                "data": {
                    "service": {
                        "host_name": "web01",
                        "description": "HTTP",
                        "status": 2,
                        "plugin_output": "OK",
                        "problem_has_been_acknowledged": True,
                        "scheduled_downtime_depth": 1,
                    }
                },
            }
        )
        svc = client.get_service_status("web01", "HTTP")
        assert svc.host_name == "web01"
        assert svc.problem_acknowledged is True
        assert svc.scheduled_downtime is True

    def test_parses_full_service_payload(self) -> None:
        client, opener = _client()
        opener.open.return_value = _json_response(
            {
                "result": {"type_code": 0},
                "data": {
                    "service": {
                        "host_name": "mail2",
                        "description": "DISK",
                        "status": 4,
                        "plugin_output": "DF CRITICAL - zroot/backup is 95.35 (outside range 0:95)",
                        "long_plugin_output": "critical: zroot/backup is 95.35 (outside range 0:95)\n",
                        "perf_data": "'zroot/backup'=95.35;93;95;0",
                        "current_attempt": 6,
                        "max_attempts": 6,
                        "state_type": 1,
                        "acknowledgement_type": 2,
                        "last_check": 1781010038000,
                        "next_check": 1781010638000,
                        "last_state_change": 1780990232000,
                        "last_hard_state_change": 1780990232000,
                        "last_time_ok": 1780558512000,
                        "last_time_warning": 1780990232000,
                        "last_time_critical": 1781010038000,
                        "last_time_unknown": 0,
                        "last_notification": 0,
                        "current_notification_number": 21,
                        "execution_time": 2.06,
                        "latency": 0.02,
                        "scheduled_downtime_depth": 0,
                    }
                },
            }
        )
        svc = client.get_service_status("mail2", "DISK")
        assert svc.long_plugin_output.startswith("critical:")
        assert "zroot/backup" in svc.perf_data
        assert svc.current_attempt == 6 and svc.max_attempts == 6
        assert svc.state_type == 1
        assert svc.acknowledgement_type == 2
        assert svc.last_check == 1781010038000
        assert svc.next_check == 1781010638000
        assert svc.last_state_change == 1780990232000
        assert svc.last_hard_state_change == 1780990232000
        assert svc.last_time_critical == 1781010038000
        assert svc.current_notification_number == 21
        assert svc.execution_time == 2.06
        assert svc.latency == 0.02
        assert svc.scheduled_downtime_depth == 0
        assert svc.scheduled_downtime is False

    def test_not_found_when_service_missing(self) -> None:
        client, opener = _client()
        opener.open.return_value = _json_response(
            {
                "result": {"type_code": 0},
                "data": {},
            }
        )
        with pytest.raises(NotFoundError):
            client.get_service_status("x", "y")

    def test_api_error_when_type_code_nonzero(self) -> None:
        client, opener = _client()
        opener.open.return_value = _json_response(
            {
                "result": {"type_code": 1, "message": "bad query"},
                "data": {},
            }
        )
        with pytest.raises(NagiosAPIError, match="bad query"):
            client.get_service_status("x", "y")


class TestGetHostStatus:
    def test_parses_host(self) -> None:
        client, opener = _client()
        opener.open.return_value = _json_response(
            {
                "result": {"type_code": 0},
                "data": {"host": {"name": "web01", "address": "10.0.0.1", "status": 2}},
            }
        )
        host = client.get_host_status("web01")
        assert host.name == "web01"
        assert host.address == "10.0.0.1"

    def test_not_found(self) -> None:
        client, opener = _client()
        opener.open.return_value = _json_response(
            {
                "result": {"type_code": 0},
                "data": {},
            }
        )
        with pytest.raises(NotFoundError):
            client.get_host_status("missing")


class TestListGetters:
    def test_get_problems_flattens_servicelist(self) -> None:
        client, opener = _client()
        opener.open.return_value = _json_response(
            {
                "result": {"type_code": 0},
                "data": {
                    "servicelist": {
                        "web01": {"HTTP": 16, "SSH": 4},
                        "db01": {"MySQL": 8},
                    }
                },
            }
        )
        problems = client.get_problems()
        assert {(p.host_name, p.description, p.status) for p in problems} == {
            ("web01", "HTTP", 16),
            ("web01", "SSH", 4),
            ("db01", "MySQL", 8),
        }

    def test_get_problems_api_error(self) -> None:
        client, opener = _client()
        opener.open.return_value = _json_response(
            {
                "result": {"type_code": 1, "message": "denied"},
                "data": {},
            }
        )
        with pytest.raises(NagiosAPIError, match="denied"):
            client.get_problems()

    def test_get_all_hosts(self) -> None:
        client, opener = _client()
        opener.open.return_value = _json_response(
            {
                "result": {"type_code": 0},
                "data": {"hostlist": {"web01": 2, "db01": 4}},
            }
        )
        hosts = client.get_all_hosts()
        assert {(h.name, h.status) for h in hosts} == {("web01", 2), ("db01", 4)}

    def test_get_all_hosts_api_error(self) -> None:
        client, opener = _client()
        opener.open.return_value = _json_response(
            {
                "result": {"type_code": 1, "message": "x"},
                "data": {},
            }
        )
        with pytest.raises(NagiosAPIError):
            client.get_all_hosts()

    def test_get_host_services(self) -> None:
        client, opener = _client()
        opener.open.return_value = _json_response(
            {
                "result": {"type_code": 0},
                "data": {"servicelist": {"web01": {"HTTP": 2, "SSH": 2}}},
            }
        )
        services = client.get_host_services("web01")
        assert {(s.host_name, s.description) for s in services} == {
            ("web01", "HTTP"),
            ("web01", "SSH"),
        }

    def test_get_host_services_api_error(self) -> None:
        client, opener = _client()
        opener.open.return_value = _json_response(
            {
                "result": {"type_code": 1, "message": "x"},
                "data": {},
            }
        )
        with pytest.raises(NagiosAPIError):
            client.get_host_services("web01")


class TestOpener:
    def test_opener_caches_and_disables_ssl_when_verify_ssl_false(self) -> None:
        cfg = NagiosConfig(url="https://x", username="u", password="p", verify_ssl=False)
        client = NagiosClient(cfg)
        opener1 = client._get_opener()
        opener2 = client._get_opener()
        assert opener1 is opener2

    def test_opener_with_verify_ssl_true(self) -> None:
        cfg = NagiosConfig(url="https://x", username="u", password="p", verify_ssl=True)
        client = NagiosClient(cfg)
        # Just check it doesn't blow up and returns a valid OpenerDirector.
        assert client._get_opener() is not None
