"""Tests for configuration module."""

import os
import tempfile

import pytest

from nagioscli.core.config import NagiosConfig, load_config
from nagioscli.core.exceptions import ConfigurationError


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self) -> None:
        """Test loading a valid configuration file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("""
[nagios]
url = http://nagios.example.com/nagios
username = testuser
password = testpass

[settings]
timeout = 60
verify_ssl = true
""")
            f.flush()

            try:
                config = load_config(f.name)

                assert config.url == "http://nagios.example.com/nagios"
                assert config.username == "testuser"
                assert config.password == "testpass"
                assert config.timeout == 60
                assert config.verify_ssl is True
            finally:
                os.unlink(f.name)

    def test_missing_url(self) -> None:
        """Test that missing URL raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("""
[nagios]
username = testuser
password = testpass
""")
            f.flush()

            try:
                with pytest.raises(ConfigurationError) as exc_info:
                    load_config(f.name)

                assert "url" in str(exc_info.value).lower()
            finally:
                os.unlink(f.name)

    def test_missing_username(self) -> None:
        """Test that missing username raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("""
[nagios]
url = http://nagios.example.com/nagios
password = testpass
""")
            f.flush()

            try:
                with pytest.raises(ConfigurationError) as exc_info:
                    load_config(f.name)

                assert "username" in str(exc_info.value).lower()
            finally:
                os.unlink(f.name)

    def test_missing_nagios_section(self) -> None:
        """Test that missing [nagios] section raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("""
[settings]
timeout = 60
""")
            f.flush()

            try:
                with pytest.raises(ConfigurationError) as exc_info:
                    load_config(f.name)

                assert "nagios" in str(exc_info.value).lower()
            finally:
                os.unlink(f.name)

    def test_file_not_found(self) -> None:
        """Test that missing file raises error."""
        with pytest.raises(ConfigurationError) as exc_info:
            load_config("/nonexistent/path/config.ini")

        assert "not found" in str(exc_info.value).lower()

    def test_pass_path_auth(self) -> None:
        """Test configuration with pass_path authentication."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write("""
[nagios]
url = http://nagios.example.com/nagios
username = testuser

[auth]
method = pass_path
pass_path = nagios/testuser
""")
            f.flush()

            try:
                config = load_config(f.name)

                assert config.password is None
                assert config.pass_path == "nagios/testuser"
            finally:
                os.unlink(f.name)


class TestNagiosConfig:
    """Tests for NagiosConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        config = NagiosConfig(
            url="http://nagios.example.com",
            username="testuser",
        )

        assert config.password is None
        assert config.pass_path is None
        assert config.timeout == 30
        assert config.verify_ssl is False
