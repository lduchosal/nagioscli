"""Check commands for CLI."""

import sys
from typing import Any

import click

from nagioscli.core.client import NagiosClient
from nagioscli.core.config import load_config
from nagioscli.core.exceptions import NagiosAPIError

from ..decorators import common_options
from ..handlers import OutputFormatter, handle_error


def register_check_commands(main_group: Any) -> None:
    """Register check commands with the main CLI group."""

    @main_group.command("check")
    @click.argument("hostname")
    @click.argument("service")
    @common_options
    def check_cmd(
        hostname: str,
        service: str,
        config: str,
        verbose: int,
    ) -> None:
        """Force immediate service check."""
        try:
            cfg = load_config(config)
            client = NagiosClient(cfg, verbose=verbose)

            OutputFormatter.format_verbose(f"Forcing check for {hostname}/{service}", verbose)

            success = client.force_service_check(hostname, service)

            if success:
                click.echo(f"Force check submitted for {hostname}/{service}")
            else:
                click.echo(f"Failed to submit force check for {hostname}/{service}")

        except Exception as e:
            handle_error(e, verbose)

    @main_group.command("check-host")
    @click.argument("hostname")
    @common_options
    def check_host_cmd(
        hostname: str,
        config: str,
        verbose: int,
    ) -> None:
        """Force immediate host check (runs the host's own check_command)."""
        try:
            cfg = load_config(config)
            client = NagiosClient(cfg, verbose=verbose)

            OutputFormatter.format_verbose(f"Forcing check for host {hostname}", verbose)

            success = client.force_host_check(hostname)

            if success:
                click.echo(f"Force check submitted for host {hostname}")
            else:
                click.echo(f"Failed to submit force check for host {hostname}")

        except Exception as e:
            handle_error(e, verbose)

    @main_group.command("check-problems")
    @click.argument("service", required=False)
    @common_options
    def check_problems_cmd(
        service: str | None,
        config: str,
        verbose: int,
    ) -> None:
        """Force immediate check of every service in error (warning, critical, unknown).

        SERVICE optionally restricts the run to services with that exact
        description (case-insensitive), across all hosts. Example:

            nagioscli check-problems PKGVULN
        """
        try:
            cfg = load_config(config)
            client = NagiosClient(cfg, verbose=verbose)

            OutputFormatter.format_verbose(
                f"Querying services with problems from {cfg.url}", verbose
            )

            problems = client.get_problems()
            if service is not None:
                wanted = service.lower()
                problems = [svc for svc in problems if svc.description.lower() == wanted]

            if not problems:
                suffix = f" matching {service}" if service else ""
                click.echo(f"No services in error{suffix}")
                return

            failures = 0
            for svc in problems:
                status_text = OutputFormatter.format_service_status(svc.status)
                try:
                    success = client.force_service_check(svc.host_name, svc.description)
                except NagiosAPIError as exc:
                    # Keep going: one host failing must not abort the batch.
                    success = False
                    OutputFormatter.format_verbose(f"  error: {exc}", verbose)
                if success:
                    click.echo(
                        f"Force check submitted for {svc.host_name}/{svc.description}"
                        f" ({status_text})"
                    )
                else:
                    failures += 1
                    click.echo(
                        f"Failed to submit force check for {svc.host_name}/{svc.description}"
                        f" ({status_text})"
                    )

            click.echo(f"\nSubmitted {len(problems) - failures}/{len(problems)} force check(s)")
            if failures:
                sys.exit(1)

        except Exception as e:
            handle_error(e, verbose)

    @main_group.command("check-host-services")
    @click.argument("hostname")
    @common_options
    def check_host_services_cmd(
        hostname: str,
        config: str,
        verbose: int,
    ) -> None:
        """Force immediate check of every service of a host."""
        try:
            cfg = load_config(config)
            client = NagiosClient(cfg, verbose=verbose)

            OutputFormatter.format_verbose(
                f"Forcing check of all services for host {hostname}", verbose
            )

            success = client.force_host_services_check(hostname)

            if success:
                click.echo(f"Force check of all services submitted for host {hostname}")
            else:
                click.echo(f"Failed to submit force check of all services for host {hostname}")

        except Exception as e:
            handle_error(e, verbose)
