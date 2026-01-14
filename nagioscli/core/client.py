"""Nagios HTTP API client."""

import json
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

from .auth import get_credentials
from .config import NagiosConfig
from .exceptions import NagiosAPIError, NotFoundError
from .models import Host, Service


class NagiosClient:
    """HTTP client for Nagios Core JSON API."""

    def __init__(self, config: NagiosConfig, verbose: int = 0) -> None:
        """Initialize the Nagios client.

        Args:
            config: NagiosConfig object
            verbose: Verbosity level
        """
        self.config = config
        self.verbose = verbose
        self._opener: Optional[urllib.request.OpenerDirector] = None

    def _get_opener(self) -> urllib.request.OpenerDirector:
        """Get or create HTTP opener with authentication."""
        if self._opener is None:
            username, password = get_credentials(self.config)

            password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(None, self.config.url, username, password)
            auth_handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
            self._opener = urllib.request.build_opener(auth_handler)

        return self._opener

    def _request(self, endpoint: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Make HTTP request to Nagios API.

        Args:
            endpoint: API endpoint (e.g., 'statusjson.cgi')
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            NagiosAPIError: If request fails
        """
        url = f"{self.config.url}/cgi-bin/{endpoint}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        if self.verbose >= 2:
            print(f"DEBUG: GET {url}")

        opener = self._get_opener()

        try:
            response = opener.open(url, timeout=self.config.timeout)
            content = response.read().decode("utf-8")

            if self.verbose >= 3:
                print(f"DEBUG: Response: {content[:500]}")

            return json.loads(content)

        except urllib.error.HTTPError as e:
            raise NagiosAPIError(f"HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise NagiosAPIError(f"Connection error: {e.reason}")
        except json.JSONDecodeError as e:
            raise NagiosAPIError(f"Invalid JSON response: {e}")

    def _post(self, endpoint: str, data: Dict[str, str]) -> str:
        """Make HTTP POST request to Nagios API.

        Args:
            endpoint: API endpoint (e.g., 'cmd.cgi')
            data: POST data

        Returns:
            Response content

        Raises:
            NagiosAPIError: If request fails
        """
        url = f"{self.config.url}/cgi-bin/{endpoint}"
        encoded_data = urllib.parse.urlencode(data).encode("utf-8")

        if self.verbose >= 2:
            print(f"DEBUG: POST {url}")
            print(f"DEBUG: Data: {data}")

        opener = self._get_opener()
        request = urllib.request.Request(url, data=encoded_data, method="POST")

        try:
            response = opener.open(request, timeout=self.config.timeout)
            content = response.read().decode("utf-8")

            if self.verbose >= 3:
                print(f"DEBUG: Response: {content[:500]}")

            return content

        except urllib.error.HTTPError as e:
            raise NagiosAPIError(f"HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise NagiosAPIError(f"Connection error: {e.reason}")

    def get_service_status(self, hostname: str, service: str) -> Service:
        """Get status of a specific service.

        Args:
            hostname: Host name
            service: Service description

        Returns:
            Service object

        Raises:
            NotFoundError: If service not found
            NagiosAPIError: If API request fails
        """
        params = {
            "query": "service",
            "hostname": hostname,
            "servicedescription": service,
        }

        data = self._request("statusjson.cgi", params)

        if data.get("result", {}).get("type_code") != 0:
            raise NagiosAPIError(data.get("result", {}).get("message", "Unknown error"))

        svc_data = data.get("data", {}).get("service")
        if not svc_data:
            raise NotFoundError(f"Service not found: {hostname}/{service}")

        return self._parse_service(svc_data)

    def get_host_status(self, hostname: str) -> Host:
        """Get status of a specific host.

        Args:
            hostname: Host name

        Returns:
            Host object

        Raises:
            NotFoundError: If host not found
            NagiosAPIError: If API request fails
        """
        params = {
            "query": "host",
            "hostname": hostname,
        }

        data = self._request("statusjson.cgi", params)

        if data.get("result", {}).get("type_code") != 0:
            raise NagiosAPIError(data.get("result", {}).get("message", "Unknown error"))

        host_data = data.get("data", {}).get("host")
        if not host_data:
            raise NotFoundError(f"Host not found: {hostname}")

        return self._parse_host(host_data)

    def get_problems(self) -> List[Service]:
        """Get all services with problems (warning, critical, unknown).

        Returns:
            List of Service objects with problems
        """
        params = {
            "query": "servicelist",
            "servicestatus": "warning critical unknown",
        }

        data = self._request("statusjson.cgi", params)

        if data.get("result", {}).get("type_code") != 0:
            raise NagiosAPIError(data.get("result", {}).get("message", "Unknown error"))

        services = []
        servicelist = data.get("data", {}).get("servicelist", {})

        for hostname, host_services in servicelist.items():
            for svc_name, status in host_services.items():
                services.append(
                    Service(
                        host_name=hostname,
                        description=svc_name,
                        status=status,
                        plugin_output="",
                    )
                )

        return services

    def get_all_hosts(self) -> List[Host]:
        """Get all monitored hosts.

        Returns:
            List of Host objects
        """
        params = {
            "query": "hostlist",
        }

        data = self._request("statusjson.cgi", params)

        if data.get("result", {}).get("type_code") != 0:
            raise NagiosAPIError(data.get("result", {}).get("message", "Unknown error"))

        hosts = []
        hostlist = data.get("data", {}).get("hostlist", {})

        for hostname, status in hostlist.items():
            hosts.append(
                Host(
                    name=hostname,
                    address="",
                    status=status,
                    plugin_output="",
                )
            )

        return hosts

    def get_host_services(self, hostname: str) -> List[Service]:
        """Get all services for a specific host.

        Args:
            hostname: Host name

        Returns:
            List of Service objects
        """
        params = {
            "query": "servicelist",
            "hostname": hostname,
        }

        data = self._request("statusjson.cgi", params)

        if data.get("result", {}).get("type_code") != 0:
            raise NagiosAPIError(data.get("result", {}).get("message", "Unknown error"))

        services = []
        servicelist = data.get("data", {}).get("servicelist", {})

        for host, host_services in servicelist.items():
            for svc_name, status in host_services.items():
                services.append(
                    Service(
                        host_name=host,
                        description=svc_name,
                        status=status,
                        plugin_output="",
                    )
                )

        return services

    def force_service_check(self, hostname: str, service: str) -> bool:
        """Force immediate service check.

        Args:
            hostname: Host name
            service: Service description

        Returns:
            True if command submitted successfully
        """
        start_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

        data = {
            "cmd_typ": "7",  # SCHEDULE_FORCED_SVC_CHECK
            "cmd_mod": "2",  # CMDMODE_COMMIT
            "host": hostname,
            "service": service,
            "start_time": start_time,
            "force_check": "on",
            "btnSubmit": "Commit",
        }

        content = self._post("cmd.cgi", data)

        return "successfully submitted" in content.lower()

    def force_host_check(self, hostname: str) -> bool:
        """Force immediate host check.

        Args:
            hostname: Host name

        Returns:
            True if command submitted successfully
        """
        start_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

        data = {
            "cmd_typ": "17",  # SCHEDULE_FORCED_HOST_CHECK
            "cmd_mod": "2",  # CMDMODE_COMMIT
            "host": hostname,
            "start_time": start_time,
            "force_check": "on",
            "btnSubmit": "Commit",
        }

        content = self._post("cmd.cgi", data)

        return "successfully submitted" in content.lower()

    def acknowledge_service(self, hostname: str, service: str, comment: str) -> bool:
        """Acknowledge a service problem.

        Args:
            hostname: Host name
            service: Service description
            comment: Acknowledgement comment

        Returns:
            True if command submitted successfully
        """
        data = {
            "cmd_typ": "34",  # ACKNOWLEDGE_SVC_PROBLEM
            "cmd_mod": "2",  # CMDMODE_COMMIT
            "host": hostname,
            "service": service,
            "com_data": comment,
            "sticky_ack": "on",
            "send_notification": "on",
            "btnSubmit": "Commit",
        }

        content = self._post("cmd.cgi", data)

        return "successfully submitted" in content.lower()

    def acknowledge_host(self, hostname: str, comment: str) -> bool:
        """Acknowledge a host problem.

        Args:
            hostname: Host name
            comment: Acknowledgement comment

        Returns:
            True if command submitted successfully
        """
        data = {
            "cmd_typ": "33",  # ACKNOWLEDGE_HOST_PROBLEM
            "cmd_mod": "2",  # CMDMODE_COMMIT
            "host": hostname,
            "com_data": comment,
            "sticky_ack": "on",
            "send_notification": "on",
            "btnSubmit": "Commit",
        }

        content = self._post("cmd.cgi", data)

        return "successfully submitted" in content.lower()

    def _parse_service(self, data: Dict[str, Any]) -> Service:
        """Parse service data from API response."""
        return Service(
            host_name=data.get("host_name", ""),
            description=data.get("description", ""),
            status=data.get("status", 16),
            plugin_output=data.get("plugin_output", ""),
            current_attempt=data.get("current_attempt", 0),
            max_attempts=data.get("max_attempts", 0),
            checks_enabled=data.get("checks_enabled", True),
            notifications_enabled=data.get("notifications_enabled", True),
            problem_acknowledged=data.get("problem_has_been_acknowledged", False),
            scheduled_downtime=data.get("scheduled_downtime_depth", 0) > 0,
            perf_data=data.get("perf_data", ""),
        )

    def _parse_host(self, data: Dict[str, Any]) -> Host:
        """Parse host data from API response."""
        return Host(
            name=data.get("name", ""),
            address=data.get("address", ""),
            status=data.get("status", 8),
            plugin_output=data.get("plugin_output", ""),
            checks_enabled=data.get("checks_enabled", True),
            notifications_enabled=data.get("notifications_enabled", True),
            problem_acknowledged=data.get("problem_has_been_acknowledged", False),
            scheduled_downtime=data.get("scheduled_downtime_depth", 0) > 0,
        )
