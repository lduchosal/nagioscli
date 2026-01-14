"""Services command for CLI."""

import json
from typing import Any

import click

from nagioscli.core.client import NagiosClient
from nagioscli.core.config import load_config

from ..decorators import common_options, output_options
from ..handlers import OutputFormatter, handle_error


def register_services_commands(main_group: Any) -> None:
    """Register services commands with the main CLI group."""

    @main_group.command("services")
    @click.argument("hostname")
    @common_options
    @output_options
    def services_cmd(
        hostname: str,
        config: str,
        verbose: int,
        output_json: bool,
        quiet: bool,
    ) -> None:
        """List all services for a host."""
        try:
            cfg = load_config(config)
            client = NagiosClient(cfg, verbose=verbose)

            OutputFormatter.format_verbose(
                f"Querying services for {hostname}", verbose
            )

            services = client.get_host_services(hostname)

            if output_json:
                output = [
                    {
                        "host": svc.host_name,
                        "service": svc.description,
                        "status": svc.status,
                        "status_text": OutputFormatter.format_service_status(svc.status),
                    }
                    for svc in services
                ]
                click.echo(json.dumps(output, indent=2))
            elif quiet:
                for svc in services:
                    click.echo(svc.description)
            else:
                for svc in services:
                    status_text = OutputFormatter.format_service_status(svc.status)
                    click.echo(f"{status_text:8} {svc.description}")

                click.echo(f"\nTotal: {len(services)} service(s)")

        except Exception as e:
            handle_error(e, verbose)
