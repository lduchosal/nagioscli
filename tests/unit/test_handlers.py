"""Tests for nagioscli.cli.handlers (error mapping + formatters)."""

import pytest

from nagioscli.cli.handlers import OutputFormatter, handle_error
from nagioscli.core.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NagiosAPIError,
    NotFoundError,
)


class TestHandleError:
    @pytest.mark.parametrize(
        "exc,expected_code",
        [
            (ConfigurationError("cfg"), 2),
            (AuthenticationError("auth"), 3),
            (NagiosAPIError("api"), 4),
            (NotFoundError("nope"), 5),
            (RuntimeError("other"), 1),
        ],
    )
    def test_exit_codes(
        self, exc: Exception, expected_code: int, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as ex:
            handle_error(exc)
        assert ex.value.code == expected_code

    def test_verbose_prints_debug(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            handle_error(NagiosAPIError("x"), verbose=1)
        err = capsys.readouterr().err
        assert "DEBUG: NagiosAPIError" in err


class TestOutputFormatter:
    def test_format_verbose_below_threshold_silent(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        OutputFormatter.format_verbose("hi", verbose_level=0)
        assert capsys.readouterr().err == ""

    def test_format_verbose_above_threshold_prints(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        OutputFormatter.format_verbose("hi", verbose_level=2)
        assert "DEBUG: hi" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "code,text",
        [(2, "OK"), (4, "WARNING"), (8, "UNKNOWN"), (16, "CRITICAL"), (99, "UNKNOWN(99)")],
    )
    def test_format_service_status(self, code: int, text: str) -> None:
        assert OutputFormatter.format_service_status(code) == text

    @pytest.mark.parametrize(
        "code,text",
        [(2, "UP"), (4, "DOWN"), (8, "UNREACHABLE"), (99, "UNKNOWN(99)")],
    )
    def test_format_host_status(self, code: int, text: str) -> None:
        assert OutputFormatter.format_host_status(code) == text
