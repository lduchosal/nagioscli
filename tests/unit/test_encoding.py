"""Tests for tolerant decoding of Nagios responses and tolerant stdout (ken #1104).

Nagios CGIs return plugin output as raw bytes with no declared encoding.
A Windows plugin on a French locale emits cp1252 inside an otherwise
UTF-8 body; strict decoding used to crash the whole command with no
output at all. These tests pin the production chain: raw cp1252 bytes in
``statusjson.cgi`` -> readable ``status service`` output, including on a
cp1252 stdout that cannot encode every character.
"""

import io
import json
from email.message import Message
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from nagioscli.cli import _tolerate_unencodable_stdout
from nagioscli.cli import main as cli_main
from nagioscli.core.client import NagiosClient
from nagioscli.core.config import NagiosConfig
from nagioscli.core.encoding import CP1252_FALLBACK, decode_body

# Production case (ken #1585): check_by_ssh -> PowerShell on a French Windows.
# Only the plugin output is cp1252; the JSON envelope around it is plain ASCII.
_PLUGIN_OUTPUT_CP1252 = (
    b"UNKNOWN - check_by_ssh: Remote command execution failed: L'argument "
    b"\xabc:/programdata/nagioscmd/scripts/check_win_firewall.ps1\xbb "
    b"du param\xe8tre -File n'existe pas.\xae"
)
_PLUGIN_OUTPUT_TEXT = (
    "UNKNOWN - check_by_ssh: Remote command execution failed: L'argument "
    "«c:/programdata/nagioscmd/scripts/check_win_firewall.ps1» "
    "du paramètre -File n'existe pas.®"
)


def _raw_response(body: bytes) -> MagicMock:
    response = MagicMock()
    response.headers = Message()
    response.read.return_value = body
    return response


def _service_body(plugin_output: bytes, long_plugin_output: bytes = b"") -> bytes:
    return (
        b'{"result": {"type_code": 0}, "data": {"service": {'
        b'"host_name": "petit-tonnerre.arcantel.dev", "description": "FW", "status": 8, '
        b'"plugin_output": "' + plugin_output + b'", '
        b'"long_plugin_output": "' + long_plugin_output + b'"}}}'
    )


def _client(opener: MagicMock) -> NagiosClient:
    cfg = NagiosConfig(url="https://nagios.example.com/nagios", username="u", password="p")
    client = NagiosClient(cfg)
    client._opener = opener
    return client


# -------------------------------------------------------------- decode_body --


class TestDecodeBody:
    def test_valid_utf8_is_untouched(self) -> None:
        text = "paramètre « ok » — ✓"
        assert decode_body(text.encode("utf-8")) == text

    def test_cp1252_bytes_are_read_as_cp1252(self) -> None:
        assert decode_body(_PLUGIN_OUTPUT_CP1252) == _PLUGIN_OUTPUT_TEXT

    def test_mixed_utf8_and_cp1252_in_one_body(self) -> None:
        body = "host é".encode() + b" / plugin \xe9"
        assert decode_body(body) == "host é / plugin é"

    def test_truncated_utf8_lead_byte_does_not_swallow_following_ascii(self) -> None:
        # 0xe9 is a 3-byte UTF-8 lead: the next ASCII bytes must survive.
        assert decode_body(b"caf\xe9 ok") == "café ok"

    def test_bytes_undefined_in_cp1252_become_replacement_char(self) -> None:
        assert decode_body(b"a\x81b") == "a\ufffdb"

    def test_handler_rejects_encode_errors(self) -> None:
        with pytest.raises(UnicodeEncodeError):
            "✓".encode("ascii", errors=CP1252_FALLBACK)


# ------------------------------------------------------------------- client --


class TestClientDecoding:
    def test_get_service_status_with_cp1252_plugin_output(self) -> None:
        opener = MagicMock()
        opener.open.return_value = _raw_response(
            _service_body(_PLUGIN_OUTPUT_CP1252, long_plugin_output=b"d\xe9tail")
        )

        svc = _client(opener).get_service_status("petit-tonnerre.arcantel.dev", "FW")

        assert svc.plugin_output == _PLUGIN_OUTPUT_TEXT
        assert svc.long_plugin_output == "détail"
        assert svc.status_text == "UNKNOWN"

    def test_cmd_post_with_cp1252_html_still_succeeds(self) -> None:
        opener = MagicMock()
        opener.open.side_effect = [
            _raw_response(
                b"<p>Commentaire \xab\xe9t\xe9\xbb</p><input name='nagFormId' value='T'>"
            ),
            _raw_response(b"<p>R\xe9sultat: successfully submitted</p>"),
        ]

        assert _client(opener).acknowledge_service("host01", "FW", "vu") is True


# ---------------------------------------------------------------------- CLI --


@pytest.fixture
def real_client_opener(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Run the real NagiosClient behind ``status``, with only the opener stubbed."""
    opener = MagicMock()
    cfg = NagiosConfig(url="https://nagios.example.com/nagios", username="u", password="p")
    monkeypatch.setattr("nagioscli.cli.commands.status.load_config", lambda _path: cfg)
    monkeypatch.setattr(NagiosClient, "_get_opener", lambda _self: opener)
    return opener


class TestStatusServiceRegression:
    def test_text_output(self, real_client_opener: MagicMock) -> None:
        real_client_opener.open.return_value = _raw_response(_service_body(_PLUGIN_OUTPUT_CP1252))

        result = CliRunner().invoke(
            cli_main, ["status", "service", "petit-tonnerre.arcantel.dev", "FW"]
        )

        assert result.exit_code == 0, result.output
        assert f"Output: {_PLUGIN_OUTPUT_TEXT}" in result.output

    def test_json_output(self, real_client_opener: MagicMock) -> None:
        real_client_opener.open.return_value = _raw_response(_service_body(_PLUGIN_OUTPUT_CP1252))

        result = CliRunner().invoke(
            cli_main, ["status", "service", "petit-tonnerre.arcantel.dev", "FW", "--json"]
        )

        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["output"] == _PLUGIN_OUTPUT_TEXT

    def test_cp1252_stdout_does_not_crash_on_unencodable_char(
        self, real_client_opener: MagicMock
    ) -> None:
        # 0x81 is undefined in cp1252 -> U+FFFD, which a cp1252 stdout can't encode.
        real_client_opener.open.return_value = _raw_response(_service_body(b"UNKNOWN \x81 x"))

        result = CliRunner(charset="cp1252").invoke(
            cli_main, ["status", "service", "petit-tonnerre.arcantel.dev", "FW"]
        )

        assert result.exit_code == 0, result.output
        assert "Output: UNKNOWN ? x" in result.output


class TestTolerateUnencodableStdout:
    def test_strict_stdout_switches_to_replace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        monkeypatch.setattr("sys.stdout", stream)

        _tolerate_unencodable_stdout()

        assert stream.errors == "replace"

    def test_user_chosen_policy_is_kept(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="backslashreplace")
        monkeypatch.setattr("sys.stdout", stream)

        _tolerate_unencodable_stdout()

        assert stream.errors == "backslashreplace"

    def test_non_textiowrapper_stdout_is_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.stdout", io.StringIO())

        _tolerate_unencodable_stdout()
