"""Mock Nagios client for fixture tests."""

import json
from pathlib import Path

from nagioscli.core.exceptions import NotFoundError
from nagioscli.core.models import Host, Service


class MockNagiosClient:
    """Mock Nagios client using fixture data."""

    def __init__(self) -> None:
        """Initialize with fixture data."""
        fixtures_dir = Path(__file__).parent

        # Load service data
        with open(fixtures_dir / "service_data.json") as f:
            self.service_data = json.load(f)

        # Load host data
        with open(fixtures_dir / "host_data.json") as f:
            self.host_data = json.load(f)

    def get_service_status(self, hostname: str, service: str) -> Service:
        """Get service status from fixtures."""
        key = f"{hostname}/{service}"
        svc_data = self.service_data.get("services", {}).get(key)
        if not svc_data:
            raise NotFoundError(f"Service not found: {key}")

        return Service(
            host_name=svc_data.get("host_name", hostname),
            description=svc_data.get("description", service),
            status=svc_data.get("status", 16),
            plugin_output=svc_data.get("plugin_output", ""),
        )

    def get_host_status(self, hostname: str) -> Host:
        """Get host status from fixtures."""
        host_data = self.host_data.get("hosts", {}).get(hostname)
        if not host_data:
            raise NotFoundError(f"Host not found: {hostname}")

        return Host(
            name=host_data.get("name", hostname),
            address=host_data.get("address", ""),
            status=host_data.get("status", 8),
            plugin_output=host_data.get("plugin_output", ""),
        )

    def get_problems(self) -> list[Service]:
        """Get all services with problems from fixtures."""
        problems = []
        for _key, svc_data in self.service_data.get("services", {}).items():
            if svc_data.get("status", 2) != 2:  # Not OK
                problems.append(
                    Service(
                        host_name=svc_data.get("host_name", ""),
                        description=svc_data.get("description", ""),
                        status=svc_data.get("status", 16),
                        plugin_output=svc_data.get("plugin_output", ""),
                    )
                )
        return problems

    def get_all_hosts(self) -> list[Host]:
        """Get all hosts from fixtures."""
        hosts = []
        for hostname, host_data in self.host_data.get("hosts", {}).items():
            hosts.append(
                Host(
                    name=host_data.get("name", hostname),
                    address=host_data.get("address", ""),
                    status=host_data.get("status", 2),
                    plugin_output=host_data.get("plugin_output", ""),
                )
            )
        return hosts

    def get_host_services(self, hostname: str) -> list[Service]:
        """Get all services for a host from fixtures."""
        services = []
        for _key, svc_data in self.service_data.get("services", {}).items():
            if svc_data.get("host_name") == hostname:
                services.append(
                    Service(
                        host_name=svc_data.get("host_name", ""),
                        description=svc_data.get("description", ""),
                        status=svc_data.get("status", 2),
                        plugin_output=svc_data.get("plugin_output", ""),
                    )
                )
        return services

    def force_service_check(self, hostname: str, service: str) -> bool:
        """Mock force service check."""
        return True

    def force_host_check(self, hostname: str) -> bool:
        """Mock force host check."""
        return True

    def acknowledge_service(self, hostname: str, service: str, comment: str) -> bool:
        """Mock acknowledge service."""
        return True

    def acknowledge_host(self, hostname: str, comment: str) -> bool:
        """Mock acknowledge host."""
        return True
