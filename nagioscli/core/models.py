"""Data models for nagioscli."""

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum


class ServiceStatus(IntEnum):
    """Nagios service status codes."""

    OK = 2
    WARNING = 4
    CRITICAL = 8
    UNKNOWN = 16


class HostStatus(IntEnum):
    """Nagios host status codes."""

    UP = 2
    DOWN = 4
    UNREACHABLE = 8


@dataclass
class Service:
    """Nagios service status."""

    host_name: str
    description: str
    status: int
    plugin_output: str
    last_check: datetime | None = None
    last_state_change: datetime | None = None
    current_attempt: int = 0
    max_attempts: int = 0
    checks_enabled: bool = True
    notifications_enabled: bool = True
    problem_acknowledged: bool = False
    scheduled_downtime: bool = False
    perf_data: str = ""

    @property
    def status_text(self) -> str:
        """Return human-readable status."""
        status_map = {
            ServiceStatus.OK: "OK",
            ServiceStatus.WARNING: "WARNING",
            ServiceStatus.CRITICAL: "CRITICAL",
            ServiceStatus.UNKNOWN: "UNKNOWN",
        }
        return status_map.get(ServiceStatus(self.status), f"UNKNOWN({self.status})")

    @property
    def is_problem(self) -> bool:
        """Check if service is in problem state."""
        return self.status != ServiceStatus.OK


@dataclass
class Host:
    """Nagios host status."""

    name: str
    address: str
    status: int
    plugin_output: str
    last_check: datetime | None = None
    last_state_change: datetime | None = None
    checks_enabled: bool = True
    notifications_enabled: bool = True
    problem_acknowledged: bool = False
    scheduled_downtime: bool = False

    @property
    def status_text(self) -> str:
        """Return human-readable status."""
        status_map = {
            HostStatus.UP: "UP",
            HostStatus.DOWN: "DOWN",
            HostStatus.UNREACHABLE: "UNREACHABLE",
        }
        return status_map.get(HostStatus(self.status), f"UNKNOWN({self.status})")

    @property
    def is_problem(self) -> bool:
        """Check if host is in problem state."""
        return self.status != HostStatus.UP


@dataclass
class NagiosInfo:
    """Nagios server information."""

    version: str
    program_start: datetime | None = None
    last_data_update: datetime | None = None
