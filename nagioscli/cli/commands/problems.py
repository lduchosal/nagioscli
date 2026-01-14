"""Problems command for CLI."""

import json
import sys
from typing import Any

import click

from nagioscli.core.client import NagiosClient
from nagioscli.core.config import load_config

from ..decorators import common_options, output_options
from ..handlers import OutputFormatter, handle_error


def register_problems_commands(main_group: Any) -> None:
    """Register problems commands with the main CLI group."""

    @main_group.command("problems")
    @common_options
    @output_options
    def problems_cmd(
        config: str,
        verbose: int,
        output_json: bool,
        quiet: bool,
    ) -> None:
        """List all services with problems (warning, critical, unknown)."""
        try:
            cfg = load_config(config)
            client = NagiosClient(cfg, verbose=verbose)

            OutputFormatter.format_verbose(f"Querying problems from {cfg.url}", verbose)

            services = client.get_problems()

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
                sys.exit(0 if len(services) == 0 else 1)
            else:
                if not services:
                    click.echo("No problems found")
                else:
                    for svc in services:
                        status_text = OutputFormatter.format_service_status(svc.status)
                        click.echo(f"{status_text:8} {svc.host_name} / {svc.description}")

                    click.echo(f"\nTotal: {len(services)} problem(s)")

        except Exception as e:
            handle_error(e, verbose)
