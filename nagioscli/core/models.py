"""Data models for nagioscli."""

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum


class ServiceStatus(IntEnum):
    """Nagios service status codes."""

    OK = 2
    WARNING = 4
    UNKNOWN = 8
    CRITICAL = 16


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
    long_plugin_output: str = ""
    perf_data: str = ""
    current_attempt: int = 0
    max_attempts: int = 0
    state_type: int = 0
    checks_enabled: bool = True
    notifications_enabled: bool = True
    problem_acknowledged: bool = False
    acknowledgement_type: int = 0
    scheduled_downtime: bool = False
    scheduled_downtime_depth: int = 0
    last_check: int = 0
    next_check: int = 0
    last_state_change: int = 0
    last_hard_state_change: int = 0
    last_time_ok: int = 0
    last_time_warning: int = 0
    last_time_critical: int = 0
    last_time_unknown: int = 0
    last_notification: int = 0
    current_notification_number: int = 0
    execution_time: float = 0.0
    latency: float = 0.0

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
    last_check: int = 0
    last_state_change: int = 0
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
