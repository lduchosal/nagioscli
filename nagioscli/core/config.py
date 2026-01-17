"""Configuration management for nagioscli."""

import configparser
import os
from dataclasses import dataclass
from pathlib import Path

from .exceptions import ConfigurationError


@dataclass
class NagiosConfig:
    """Nagios connection configuration."""

    url: str
    username: str
    password: str | None = None
    pass_path: str | None = None
    vouch_cookie: str | None = None
    timeout: int = 30
    verify_ssl: bool = False


def load_config(config_path: str = "nagioscli.ini") -> NagiosConfig:
    """Load configuration from file.

    Args:
        config_path: Path to configuration file

    Returns:
        NagiosConfig object

    Raises:
        ConfigurationError: If configuration is invalid
    """
    config = configparser.ConfigParser()

    config_file = _find_config_file(config_path)

    if not config_file or not os.path.exists(config_file):
        raise ConfigurationError(f"Configuration file not found: {config_path}")

    config.read(config_file)

    return _parse_config(config)


def _find_config_file(config_path: str) -> str | None:
    """Find configuration file in standard locations.

    Search order:
    1. Absolute path (if provided)
    2. Current directory
    3. User home directory (~/.nagioscli.ini)
    4. /usr/local/etc/nagioscli.ini
    """
    if os.path.isabs(config_path):
        return config_path

    # Current directory
    current_dir = Path.cwd() / config_path
    if current_dir.exists():
        return str(current_dir)

    # Home directory
    home_dir = Path.home() / f".{config_path}"
    if home_dir.exists():
        return str(home_dir)

    # System config
    system_config = Path("/usr/local/etc") / config_path
    if system_config.exists():
        return str(system_config)

    return config_path


def _parse_config(config: configparser.ConfigParser) -> NagiosConfig:
    """Parse configuration into NagiosConfig object."""
    if "nagios" not in config:
        raise ConfigurationError("Missing [nagios] section in configuration")

    nagios_section = config["nagios"]

    url = nagios_section.get("url")
    if not url:
        raise ConfigurationError("Missing 'url' in [nagios] section")

    username = nagios_section.get("username")
    if not username:
        raise ConfigurationError("Missing 'username' in [nagios] section")

    # Get password from various sources
    password = None
    pass_path = None
    vouch_cookie = None

    if "auth" in config:
        auth_section = config["auth"]
        method = auth_section.get("method", "password")

        if method == "password":
            password = auth_section.get("password")
        elif method == "pass_path":
            pass_path = auth_section.get("pass_path")
        elif method == "env_var":
            env_var = auth_section.get("env_var", "NAGIOS_PASSWORD")
            password = os.environ.get(env_var)
        elif method == "vouch_cookie":
            vouch_cookie = auth_section.get("vouch_cookie")
    else:
        # Default: try to get password directly from nagios section
        password = nagios_section.get("password")

    # Settings
    timeout = 30
    verify_ssl = False

    if "settings" in config:
        settings_section = config["settings"]
        timeout = settings_section.getint("timeout", 30)
        verify_ssl = settings_section.getboolean("verify_ssl", False)

    return NagiosConfig(
        url=url,
        username=username,
        password=password,
        pass_path=pass_path,
        vouch_cookie=vouch_cookie,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )
