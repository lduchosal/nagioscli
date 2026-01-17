"""Login command for CLI - manual Vouch cookie authentication."""

from typing import Any

import click

from nagioscli.core.auth import TOKEN_CACHE_FILE


def register_login_commands(main_group: Any) -> None:
    """Register login commands with the main CLI group."""

    @main_group.command("login")
    def login_cmd() -> None:
        """Manually enter VouchCookie value from browser.

        Steps:
        1. Open browser to your Nagios URL
        2. Authenticate via SSO
        3. Open DevTools (F12) -> Application -> Cookies
        4. Copy the VouchCookie value
        5. Paste it here
        """
        click.echo("Login - paste your VouchCookie cookie value")
        click.echo("")
        click.echo("To get the token:")
        click.echo("1. Open browser to your Nagios URL")
        click.echo("2. Authenticate via SSO")
        click.echo("3. Open DevTools (F12) -> Application -> Cookies")
        click.echo("4. Copy the VouchCookie value")
        click.echo("")
        token = click.prompt("VouchCookie", hide_input=False)

        if token:
            _save_token(token.strip())
            click.echo(f"Token saved to {TOKEN_CACHE_FILE}")
            click.echo("You can now use nagioscli commands.")
        else:
            click.echo("No token provided.", err=True)

    @main_group.command("logout")
    def logout_cmd() -> None:
        """Clear saved authentication token."""
        if TOKEN_CACHE_FILE.exists():
            TOKEN_CACHE_FILE.unlink()
            click.echo("Logged out successfully.")
        else:
            click.echo("No saved token found.")


def _save_token(token: str) -> None:
    """Save token to cache file."""
    TOKEN_CACHE_FILE.write_text(token)
    try:
        TOKEN_CACHE_FILE.chmod(0o600)
    except OSError:
        pass  # chmod may fail on Windows
