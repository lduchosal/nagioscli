"""Tests for models module."""


from nagioscli.core.models import Host, HostStatus, Service, ServiceStatus


class TestService:
    """Tests for Service model."""

    def test_status_text_ok(self) -> None:
        """Test status text for OK status."""
        service = Service(
            host_name="test.host",
            description="TestService",
            status=ServiceStatus.OK,
            plugin_output="All good",
        )

        assert service.status_text == "OK"
        assert service.is_problem is False

    def test_status_text_warning(self) -> None:
        """Test status text for WARNING status."""
        service = Service(
            host_name="test.host",
            description="TestService",
            status=ServiceStatus.WARNING,
            plugin_output="Warning message",
        )

        assert service.status_text == "WARNING"
        assert service.is_problem is True

    def test_status_text_critical(self) -> None:
        """Test status text for CRITICAL status."""
        service = Service(
            host_name="test.host",
            description="TestService",
            status=ServiceStatus.CRITICAL,
            plugin_output="Critical message",
        )

        assert service.status_text == "CRITICAL"
        assert service.is_problem is True

    def test_status_text_unknown(self) -> None:
        """Test status text for UNKNOWN status."""
        service = Service(
            host_name="test.host",
            description="TestService",
            status=ServiceStatus.UNKNOWN,
            plugin_output="Unknown message",
        )

        assert service.status_text == "UNKNOWN"
        assert service.is_problem is True


class TestHost:
    """Tests for Host model."""

    def test_status_text_up(self) -> None:
        """Test status text for UP status."""
        host = Host(
            name="test.host",
            address="192.168.1.1",
            status=HostStatus.UP,
            plugin_output="PING OK",
        )

        assert host.status_text == "UP"
        assert host.is_problem is False

    def test_status_text_down(self) -> None:
        """Test status text for DOWN status."""
        host = Host(
            name="test.host",
            address="192.168.1.1",
            status=HostStatus.DOWN,
            plugin_output="PING CRITICAL",
        )

        assert host.status_text == "DOWN"
        assert host.is_problem is True

    def test_status_text_unreachable(self) -> None:
        """Test status text for UNREACHABLE status."""
        host = Host(
            name="test.host",
            address="192.168.1.1",
            status=HostStatus.UNREACHABLE,
            plugin_output="Host unreachable",
        )

        assert host.status_text == "UNREACHABLE"
        assert host.is_problem is True


class TestServiceStatus:
    """Tests for ServiceStatus enum."""

    def test_status_values(self) -> None:
        """Test status enum values."""
        assert ServiceStatus.OK == 2
        assert ServiceStatus.WARNING == 4
        assert ServiceStatus.UNKNOWN == 8
        assert ServiceStatus.CRITICAL == 16

    def test_nagios_bitmap_regression(self) -> None:
        # Pins the Nagios statusjson.cgi bitmap (cgi/statusjson.c): a swap of
        # CRITICAL/UNKNOWN inverts every alert severity in the output.
        assert int(ServiceStatus.UNKNOWN) == 8
        assert int(ServiceStatus.CRITICAL) == 16

        service_critical = Service(
            host_name="h", description="s", status=16, plugin_output=""
        )
        service_unknown = Service(
            host_name="h", description="s", status=8, plugin_output=""
        )
        assert service_critical.status_text == "CRITICAL"
        assert service_unknown.status_text == "UNKNOWN"


class TestHostStatus:
    """Tests for HostStatus enum."""

    def test_status_values(self) -> None:
        """Test status enum values."""
        assert HostStatus.UP == 2
        assert HostStatus.DOWN == 4
        assert HostStatus.UNREACHABLE == 8
