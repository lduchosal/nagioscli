"""Commands package for CLI."""

from typing import Any

from .problems import register_problems_commands
from .status import register_status_commands
from .check import register_check_commands
from .hosts import register_hosts_commands
from .services import register_services_commands
from .ack import register_ack_commands


def register_all_commands(main_group: Any) -> None:
    """Register all commands with the main CLI group."""
    register_problems_commands(main_group)
    register_status_commands(main_group)
    register_check_commands(main_group)
    register_hosts_commands(main_group)
    register_services_commands(main_group)
    register_ack_commands(main_group)
