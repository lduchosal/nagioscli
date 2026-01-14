"""Hosts command for CLI."""

import json
from typing import Any

import click

from nagioscli.core.client import NagiosClient
from nagioscli.core.config import load_config

from ..decorators import common_options, output_options
from ..handlers import OutputFormatter, handle_error


def register_hosts_commands(main_group: Any) -> None:
    """Register hosts commands with the main CLI group."""

    @main_group.command("hosts")
    @common_options
    @output_options
    def hosts_cmd(
        config: str,
        verbose: int,
        output_json: bool,
        quiet: bool,
    ) -> None:
        """List all monitored hosts."""
        try:
            cfg = load_config(config)
            client = NagiosClient(cfg, verbose=verbose)

            OutputFormatter.format_verbose(f"Querying hosts from {cfg.url}", verbose)

            hosts = client.get_all_hosts()

            if output_json:
                output = [
                    {
                        "host": h.name,
                        "status": h.status,
                        "status_text": OutputFormatter.format_host_status(h.status),
                    }
                    for h in hosts
                ]
                click.echo(json.dumps(output, indent=2))
            elif quiet:
                for h in hosts:
                    click.echo(h.name)
            else:
                for h in hosts:
                    status_text = OutputFormatter.format_host_status(h.status)
                    click.echo(f"{status_text:12} {h.name}")

                click.echo(f"\nTotal: {len(hosts)} host(s)")

        except Exception as e:
            handle_error(e, verbose)
