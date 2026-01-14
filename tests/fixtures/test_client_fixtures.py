"""Tests using mock client fixtures."""

import pytest

from nagioscli.core.exceptions import NotFoundError
from nagioscli.core.models import HostStatus, ServiceStatus

from .mock_nagios_client import MockNagiosClient


class TestMockNagiosClient:
    """Tests for MockNagiosClient."""

    @pytest.fixture
    def client(self) -> MockNagiosClient:
        """Create mock client."""
        return MockNagiosClient()

    def test_get_service_status_ok(self, client: MockNagiosClient) -> None:
        """Test getting OK service status."""
        service = client.get_service_status("web01.example.com", "HTTP")

        assert service.host_name == "web01.example.com"
        assert service.description == "HTTP"
        assert service.status == ServiceStatus.OK
        assert "HTTP OK" in service.plugin_output

    def test_get_service_status_warning(self, client: MockNagiosClient) -> None:
        """Test getting WARNING service status."""
        service = client.get_service_status("web01.example.com", "DISK")

        assert service.status == ServiceStatus.WARNING
        assert service.is_problem is True

    def test_get_service_status_critical(self, client: MockNagiosClient) -> None:
        """Test getting CRITICAL service status."""
        service = client.get_service_status("db01.example.com", "DISK")

        assert service.status == ServiceStatus.CRITICAL
        assert service.is_problem is True

    def test_get_service_status_unknown(self, client: MockNagiosClient) -> None:
        """Test getting UNKNOWN service status."""
        service = client.get_service_status("mail01.example.com", "SMTP")

        assert service.status == ServiceStatus.UNKNOWN
        assert service.is_problem is True

    def test_get_service_status_not_found(self, client: MockNagiosClient) -> None:
        """Test service not found."""
        with pytest.raises(NotFoundError):
            client.get_service_status("nonexistent.example.com", "HTTP")

    def test_get_host_status_up(self, client: MockNagiosClient) -> None:
        """Test getting UP host status."""
        host = client.get_host_status("web01.example.com")

        assert host.name == "web01.example.com"
        assert host.address == "192.168.1.10"
        assert host.status == HostStatus.UP
        assert host.is_problem is False

    def test_get_host_status_down(self, client: MockNagiosClient) -> None:
        """Test getting DOWN host status."""
        host = client.get_host_status("mail01.example.com")

        assert host.status == HostStatus.DOWN
        assert host.is_problem is True

    def test_get_host_status_unreachable(self, client: MockNagiosClient) -> None:
        """Test getting UNREACHABLE host status."""
        host = client.get_host_status("backup01.example.com")

        assert host.status == HostStatus.UNREACHABLE
        assert host.is_problem is True

    def test_get_host_status_not_found(self, client: MockNagiosClient) -> None:
        """Test host not found."""
        with pytest.raises(NotFoundError):
            client.get_host_status("nonexistent.example.com")

    def test_get_problems(self, client: MockNagiosClient) -> None:
        """Test getting all problems."""
        problems = client.get_problems()

        assert len(problems) == 3  # DISK warning, DISK critical, SMTP unknown
        assert all(p.is_problem for p in problems)

    def test_get_all_hosts(self, client: MockNagiosClient) -> None:
        """Test getting all hosts."""
        hosts = client.get_all_hosts()

        assert len(hosts) == 4

    def test_get_host_services(self, client: MockNagiosClient) -> None:
        """Test getting services for a host."""
        services = client.get_host_services("web01.example.com")

        assert len(services) == 3  # HTTP, HTTPS, DISK

    def test_force_service_check(self, client: MockNagiosClient) -> None:
        """Test force service check."""
        result = client.force_service_check("web01.example.com", "HTTP")

        assert result is True

    def test_acknowledge_service(self, client: MockNagiosClient) -> None:
        """Test acknowledge service."""
        result = client.acknowledge_service("web01.example.com", "DISK", "Working on it")

        assert result is True
