"""Status commands for CLI."""

import json
from typing import Any

import click

from nagioscli.core.client import NagiosClient
from nagioscli.core.config import load_config

from ..decorators import common_options, output_options
from ..handlers import OutputFormatter, handle_error


def register_status_commands(main_group: Any) -> None:
    """Register status commands with the main CLI group."""

    @main_group.group("status")
    def status_group() -> None:
        """Query host and service status."""
        pass

    @status_group.command("service")
    @click.argument("hostname")
    @click.argument("service")
    @common_options
    @output_options
    def service_status_cmd(
        hostname: str,
        service: str,
        config: str,
        verbose: int,
        output_json: bool,
        quiet: bool,
    ) -> None:
        """Query status of a specific service."""
        try:
            cfg = load_config(config)
            client = NagiosClient(cfg, verbose=verbose)

            OutputFormatter.format_verbose(
                f"Querying service {hostname}/{service}", verbose
            )

            svc = client.get_service_status(hostname, service)

            if output_json:
                output = {
                    "host": svc.host_name,
                    "service": svc.description,
                    "status": svc.status,
                    "status_text": svc.status_text,
                    "output": svc.plugin_output,
                    "checks_enabled": svc.checks_enabled,
                    "notifications_enabled": svc.notifications_enabled,
                    "acknowledged": svc.problem_acknowledged,
                    "downtime": svc.scheduled_downtime,
                }
                click.echo(json.dumps(output, indent=2))
            elif quiet:
                click.echo(svc.status_text)
            else:
                click.echo(f"Host: {svc.host_name}")
                click.echo(f"Service: {svc.description}")
                click.echo(f"Status: {svc.status_text}")
                click.echo(f"Output: {svc.plugin_output}")

                if svc.problem_acknowledged:
                    click.echo("Acknowledged: Yes")
                if svc.scheduled_downtime:
                    click.echo("Downtime: Yes")

        except Exception as e:
            handle_error(e, verbose)

    @status_group.command("host")
    @click.argument("hostname")
    @common_options
    @output_options
    def host_status_cmd(
        hostname: str,
        config: str,
        verbose: int,
        output_json: bool,
        quiet: bool,
    ) -> None:
        """Query status of a specific host."""
        try:
            cfg = load_config(config)
            client = NagiosClient(cfg, verbose=verbose)

            OutputFormatter.format_verbose(f"Querying host {hostname}", verbose)

            host = client.get_host_status(hostname)

            if output_json:
                output = {
                    "host": host.name,
                    "address": host.address,
                    "status": host.status,
                    "status_text": host.status_text,
                    "output": host.plugin_output,
                    "checks_enabled": host.checks_enabled,
                    "notifications_enabled": host.notifications_enabled,
                    "acknowledged": host.problem_acknowledged,
                    "downtime": host.scheduled_downtime,
                }
                click.echo(json.dumps(output, indent=2))
            elif quiet:
                click.echo(host.status_text)
            else:
                click.echo(f"Host: {host.name}")
                click.echo(f"Address: {host.address}")
                click.echo(f"Status: {host.status_text}")
                click.echo(f"Output: {host.plugin_output}")

                if host.problem_acknowledged:
                    click.echo("Acknowledged: Yes")
                if host.scheduled_downtime:
                    click.echo("Downtime: Yes")

        except Exception as e:
            handle_error(e, verbose)
