"""Authentication management for nagioscli."""

import subprocess
from pathlib import Path

from .config import NagiosConfig
from .exceptions import AuthenticationError

# Token cache file location
TOKEN_CACHE_FILE = Path.home() / ".nagioscli_token"


def load_cached_vouch_token() -> str | None:
    """Load Vouch token from cache file if it exists.

    Returns:
        Token string or None if not cached
    """
    if TOKEN_CACHE_FILE.exists():
        return TOKEN_CACHE_FILE.read_text().strip()
    return None


def get_credentials(config: NagiosConfig) -> tuple[str, str]:
    """Get username and password from configuration.

    Args:
        config: NagiosConfig object

    Returns:
        Tuple of (username, password)

    Raises:
        AuthenticationError: If credentials cannot be obtained
    """
    # Skip credential retrieval if using Vouch cookie auth
    if config.vouch_cookie or load_cached_vouch_token():
        return config.username, ""

    username = config.username
    password = None

    if config.password:
        password = config.password
    elif config.pass_path:
        password = _get_password_from_pass(config.pass_path)
    else:
        raise AuthenticationError(
            "No password configured. Use 'nagioscli login' or set password/pass_path in config."
        )

    if not password:
        raise AuthenticationError("Failed to retrieve password")

    return username, password


def _get_password_from_pass(pass_path: str) -> str:
    """Retrieve password from pass (password-store).

    Args:
        pass_path: Path in password store (e.g., 'nagios/admin')

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
