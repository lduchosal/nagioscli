"""Authentication management for nagioscli."""

import subprocess

from .config import NagiosConfig
from .exceptions import AuthenticationError


def get_credentials(config: NagiosConfig) -> tuple[str, str]:
    """Get username and password from configuration.

    Args:
        config: NagiosConfig object

    Returns:
        Tuple of (username, password)

    Raises:
        AuthenticationError: If credentials cannot be obtained
    """
    username = config.username
    password = None

    if config.password:
        password = config.password
    elif config.pass_path:
        password = _get_password_from_pass(config.pass_path)
    else:
        raise AuthenticationError(
            "No password configured. Set password, pass_path, or env_var in config."
        )

    if not password:
        raise AuthenticationError("Failed to retrieve password")

    return username, password


def _get_password_from_pass(pass_path: str) -> str:
    """Retrieve password from pass (password-store).

    Args:
        pass_path: Path in password store (e.g., 'nagios/claude')

    Returns:
        Password string

    Raises:
        AuthenticationError: If password cannot be retrieved
    """
    try:
        result = subprocess.run(
            ["pass", pass_path],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            raise AuthenticationError(f"pass returned error: {result.stderr.strip()}")

        password = result.stdout.strip()
        if not password:
            raise AuthenticationError(f"Empty password from pass for: {pass_path}")

        return password

    except FileNotFoundError:
        raise AuthenticationError("'pass' command not found. Install password-store.") from None
    except subprocess.TimeoutExpired:
        raise AuthenticationError("Timeout waiting for pass command") from None
    except Exception as e:
        raise AuthenticationError(f"Failed to get password from pass: {e}") from e
