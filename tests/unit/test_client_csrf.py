"""Tests for CSRF preflight + start_time_format on cmd.cgi commands.

Pins the Nagios Core 4.4+ contract: every cmd.cgi POST must carry the
NagFormId cookie + the matching nagFormId hidden-field value obtained
from a GET preflight. Also covers the configurable start_time_format
(US default; Euro and ISO must round-trip through the POST body).
"""

import urllib.parse
from email.message import Message
from typing import Any
from unittest.mock import MagicMock

import pytest

from nagioscli.core.client import (
    _NAGFORM_COOKIE_RE,
    _NAGFORM_INPUT_RE,
    NagiosClient,
)
from nagioscli.core.config import NagiosConfig


def _make_response(body: str, set_cookies: list[str] | None = None) -> MagicMock:
    """Build a urllib-style response with a body and Set-Cookie headers."""
    headers = Message()
    for sc in set_cookies or []:
        headers["Set-Cookie"] = sc
    response = MagicMock()
    response.headers = headers
    response.read.return_value = body.encode("utf-8")
    return response


def _client_with_opener(opener: MagicMock, **config_overrides: Any) -> NagiosClient:
    config = NagiosConfig(
        url="https://nagios.example.com/nagios",
        username="user",
        password="pass",
        **config_overrides,
    )
    client = NagiosClient(config)
    client._opener = opener
    return client


def _decode_post_body(call_args: Any) -> dict[str, str]:
    """Pull the form-encoded POST body out of an opener.open() call."""
    request = call_args[0][0]
    return dict(urllib.parse.parse_qsl(request.data.decode("utf-8"), keep_blank_values=True))


class TestRegexes:
    def test_input_regex_single_quotes(self) -> None:
        html = "<INPUT TYPE='hidden' NAME='nagFormId' VALUE='abc123XYZ'>"
        assert _NAGFORM_INPUT_RE.search(html).group(1) == "abc123XYZ"

    def test_input_regex_double_quotes_and_attr_order(self) -> None:
        html = '<input type="hidden" value="zzz" name="nagFormId">'
        # value before name — regex requires name first, then value
        assert _NAGFORM_INPUT_RE.search(html) is None
        html2 = '<input type="hidden" name="nagFormId" value="zzz">'
        assert _NAGFORM_INPUT_RE.search(html2).group(1) == "zzz"

    def test_cookie_regex(self) -> None:
        assert _NAGFORM_COOKIE_RE.search("NagFormId=tok-1; Path=/").group(1) == "tok-1"
        assert _NAGFORM_COOKIE_RE.search("Path=/; NagFormId=tok-2; Secure").group(1) == "tok-2"
        assert _NAGFORM_COOKIE_RE.search("SomeOther=1; Path=/") is None


class TestCsrfPreflight:
    def test_force_service_check_does_preflight_then_post_with_token_and_cookie(self) -> None:
        opener = MagicMock()
        opener.open.side_effect = [
            _make_response(
                body=(
                    "<html><body><form>"
                    "<input type='hidden' name='nagFormId' value='TOKEN-42'>"
                    "</form></body></html>"
                ),
                set_cookies=["NagFormId=COOKIE-42; Path=/nagios"],
            ),
            _make_response(
                body="<p>Your command request was successfully submitted to Nagios for processing.</p>"
            ),
        ]
        client = _client_with_opener(opener)

        assert client.force_service_check("host01", "HTTP") is True

        assert opener.open.call_count == 2

        preflight_request = opener.open.call_args_list[0][0][0]
        assert preflight_request.get_method() == "GET"
        assert "cmd_typ=7" in preflight_request.full_url
        assert "host=host01" in preflight_request.full_url
        assert "service=HTTP" in preflight_request.full_url

        post_request = opener.open.call_args_list[1][0][0]
        assert post_request.get_method() == "POST"
        assert post_request.full_url == "https://nagios.example.com/nagios/cgi-bin/cmd.cgi"

        # POST body must echo the hidden form token
        body = _decode_post_body(opener.open.call_args_list[1])
        assert body["nagFormId"] == "TOKEN-42"
        assert body["cmd_typ"] == "7"
        assert body["host"] == "host01"
        assert body["service"] == "HTTP"

        # POST must carry the NagFormId cookie alongside Basic auth
        cookie_header = post_request.get_header("Cookie")
        assert cookie_header is not None
        assert "NagFormId=COOKIE-42" in cookie_header
        assert post_request.get_header("Authorization", "").startswith("Basic ")

    def test_force_host_check_uses_cmd_typ_96(self) -> None:
        # cmd_typ=96 is SCHEDULE_FORCED_HOST_CHECK (the host's own check_command).
        # cmd_typ=17 is SCHEDULE_FORCED_HOST_SVC_CHECKS (all services of host) —
        # covered separately by test_force_host_services_check.
        opener = MagicMock()
        opener.open.side_effect = [
            _make_response(
                body="<input type='hidden' name='nagFormId' value='H'>",
                set_cookies=["NagFormId=HC"],
            ),
            _make_response(body="Your command request was successfully submitted"),
        ]
        client = _client_with_opener(opener)

        assert client.force_host_check("host01") is True

        preflight_url = opener.open.call_args_list[0][0][0].full_url
        assert "cmd_typ=96" in preflight_url
        assert "service=" not in preflight_url  # host-only command

        body = _decode_post_body(opener.open.call_args_list[1])
        assert body["cmd_typ"] == "96"
        assert body["nagFormId"] == "H"
        assert "service" not in body

    def test_force_host_services_check_uses_cmd_typ_17(self) -> None:
        # cmd_typ=17 schedules a forced check of every service attached to
        # the host — distinct from cmd_typ=96 which runs the host check itself.
        opener = MagicMock()
        opener.open.side_effect = [
            _make_response(
                body="<input type='hidden' name='nagFormId' value='S'>",
                set_cookies=["NagFormId=SC"],
            ),
            _make_response(body="successfully submitted"),
        ]
        client = _client_with_opener(opener)

        assert client.force_host_services_check("host01") is True

        preflight_url = opener.open.call_args_list[0][0][0].full_url
        assert "cmd_typ=17" in preflight_url
        assert "service=" not in preflight_url

        body = _decode_post_body(opener.open.call_args_list[1])
        assert body["cmd_typ"] == "17"
        assert body["nagFormId"] == "S"

    def test_ack_service_uses_cmd_typ_34(self) -> None:
        opener = MagicMock()
        opener.open.side_effect = [
            _make_response(
                body="<input type='hidden' name='nagFormId' value='A'>",
                set_cookies=["NagFormId=AC"],
            ),
            _make_response(body="successfully submitted"),
        ]
        client = _client_with_opener(opener)

        assert client.acknowledge_service("h", "s", "looking") is True
        body = _decode_post_body(opener.open.call_args_list[1])
        assert body["cmd_typ"] == "34"
        assert body["nagFormId"] == "A"
        assert body["com_data"] == "looking"

    def test_ack_host_uses_cmd_typ_33(self) -> None:
        opener = MagicMock()
        opener.open.side_effect = [
            _make_response(
                body="<input type='hidden' name='nagFormId' value='AH'>",
                set_cookies=["NagFormId=AHC"],
            ),
            _make_response(body="successfully submitted"),
        ]
        client = _client_with_opener(opener)

        assert client.acknowledge_host("h", "wip") is True
        body = _decode_post_body(opener.open.call_args_list[1])
        assert body["cmd_typ"] == "33"
        assert body["nagFormId"] == "AH"

    def test_missing_token_still_posts_so_server_error_surfaces(self) -> None:
        # If Nagios is misconfigured and doesn't issue NagFormId we still
        # POST — letting the server's clear CSRF error reach the user beats
        # a silent client-side abort with no diagnostic.
        opener = MagicMock()
        opener.open.side_effect = [
            _make_response(body="<html>no form here</html>", set_cookies=[]),
            _make_response(body="Error: Invalid or missing CSRF cookie!"),
        ]
        client = _client_with_opener(opener)

        assert client.force_service_check("h", "s") is False
        body = _decode_post_body(opener.open.call_args_list[1])
        assert body["nagFormId"] == ""
        post_request = opener.open.call_args_list[1][0][0]
        assert post_request.get_header("Cookie") is None


class TestStartTimeFormat:
    @pytest.mark.parametrize(
        "fmt,sample_char_check",
        [
            ("%m-%d-%Y %H:%M:%S", lambda s: s[2] == "-" and s[5] == "-"),  # US default
            ("%d-%m-%Y %H:%M:%S", lambda s: s[2] == "-" and s[5] == "-"),  # Euro
            ("%Y-%m-%d %H:%M:%S", lambda s: s[4] == "-" and s[7] == "-"),  # ISO
        ],
    )
    def test_start_time_format_round_trips_into_post(
        self, fmt: str, sample_char_check: Any
    ) -> None:
        opener = MagicMock()
        opener.open.side_effect = [
            _make_response(
                body="<input type='hidden' name='nagFormId' value='T'>",
                set_cookies=["NagFormId=C"],
            ),
            _make_response(body="successfully submitted"),
        ]
        client = _client_with_opener(opener, start_time_format=fmt)

        assert client.force_service_check("h", "s") is True
        body = _decode_post_body(opener.open.call_args_list[1])
        assert "start_time" in body
        assert sample_char_check(body["start_time"]), body["start_time"]

    def test_config_default_is_us_format(self) -> None:
        # Documented default — keep US compatibility, since the historical
        # behavior was %m-%d-%Y and many users rely on it.
        config = NagiosConfig(url="u", username="u")
        assert config.start_time_format == "%m-%d-%Y %H:%M:%S"
