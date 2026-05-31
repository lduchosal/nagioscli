"""Nagios HTTP API client."""

import base64
import json
import re
import ssl
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from .auth import get_credentials, load_cached_vouch_token
from .config import NagiosConfig
from .exceptions import NagiosAPIError, NotFoundError
from .models import Host, Service

# CSRF token plumbing for Nagios Core 4.4+. The cmd.cgi flow is:
#   GET cmd.cgi?cmd_typ=... -> Set-Cookie: NagFormId=<value>
#                              + <input type=hidden name=nagFormId value=<same>>
#   POST cmd.cgi must echo both, or the server returns
#   "Error: Invalid or missing CSRF cookie!".
_NAGFORM_INPUT_RE = re.compile(
    r"""<input[^>]*\bname=['"]nagFormId['"][^>]*\bvalue=['"]([^'"]+)['"]""",
    re.IGNORECASE,
)
_NAGFORM_COOKIE_RE = re.compile(r"\bNagFormId=([^;\s]+)")


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
        self._opener: urllib.request.OpenerDirector | None = None
        self._auth_header: str | None = None
        self._vouch_cookie: str | None = None

    def _get_opener(self) -> urllib.request.OpenerDirector:
        """Get or create HTTP opener with SSL handling."""
        if self._opener is None:
            handlers: list[urllib.request.BaseHandler] = []

            if not self.config.verify_ssl:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                https_handler = urllib.request.HTTPSHandler(context=ssl_context)
                handlers.append(https_handler)

            self._opener = urllib.request.build_opener(*handlers)

        return self._opener

    def _get_auth_header(self) -> str:
        """Get Basic Auth header value (preemptive auth)."""
        if self._auth_header is None:
            username, password = get_credentials(self.config)
            credentials = f"{username}:{password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            self._auth_header = f"Basic {encoded}"
        return self._auth_header

    def _uses_nginx_token_auth(self) -> bool:
        """Check if nginx token authentication is configured."""
        return self.config.nginx_token is not None

    def _uses_vouch_auth(self) -> bool:
        """Check if Vouch cookie authentication is configured or cached."""
        return self.config.vouch_cookie is not None or load_cached_vouch_token() is not None

    def _get_vouch_cookie(self) -> str:
        """Get Vouch cookie value from cache or config."""
        if self._vouch_cookie is None:
            cached = load_cached_vouch_token()
            if cached:
                self._vouch_cookie = cached
            elif self.config.vouch_cookie:
                self._vouch_cookie = self.config.vouch_cookie
        return self._vouch_cookie or ""

    def _request(self, endpoint: str, params: dict[str, str] | None = None) -> dict[str, Any]:
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
        request = urllib.request.Request(url)
        if self.config.nginx_token is not None:
            request.add_header("X-API-Key", self.config.nginx_token)
        elif self._uses_vouch_auth():
            request.add_header("Cookie", f"VouchCookie={self._get_vouch_cookie()}")
        else:
            request.add_header("Authorization", self._get_auth_header())

        try:
            response = opener.open(request, timeout=self.config.timeout)
            content = response.read().decode("utf-8")

            if self.verbose >= 3:
                print(f"DEBUG: Response: {content[:500]}")

            result: dict[str, Any] = json.loads(content)
            return result

        except urllib.error.HTTPError as e:
            raise NagiosAPIError(f"HTTP {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise NagiosAPIError(f"Connection error: {e.reason}") from e
        except json.JSONDecodeError as e:
            raise NagiosAPIError(f"Invalid JSON response: {e}") from e

    def _apply_auth(self, request: urllib.request.Request, extra_cookies: dict[str, str] | None = None) -> None:
        """Attach the configured auth header and any extra cookies to ``request``."""
        cookies: dict[str, str] = {}
        if extra_cookies:
            cookies.update(extra_cookies)

        if self.config.nginx_token is not None:
            request.add_header("X-API-Key", self.config.nginx_token)
        elif self._uses_vouch_auth():
            cookies.setdefault("VouchCookie", self._get_vouch_cookie())
        else:
            request.add_header("Authorization", self._get_auth_header())

        if cookies:
            request.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()))

    def _csrf_preflight(self, preflight_params: dict[str, str]) -> tuple[str, str]:
        """GET cmd.cgi to obtain the CSRF cookie + hidden form token.

        Required since Nagios Core 4.4: every cmd.cgi POST must echo
        the NagFormId cookie and the matching nagFormId hidden field.

        Returns:
            (cookie value, hidden-field value). Either may be empty if
            the server didn't issue one — the caller should still POST
            so the original error surfaces to the user.
        """
        url = f"{self.config.url}/cgi-bin/cmd.cgi?{urllib.parse.urlencode(preflight_params)}"

        if self.verbose >= 2:
            print(f"DEBUG: CSRF preflight GET {url}")

        opener = self._get_opener()
        request = urllib.request.Request(url)
        self._apply_auth(request)

        try:
            response = opener.open(request, timeout=self.config.timeout)
            body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raise NagiosAPIError(f"HTTP {e.code} on CSRF preflight: {e.reason}") from e
        except urllib.error.URLError as e:
            raise NagiosAPIError(f"Connection error on CSRF preflight: {e.reason}") from e

        cookie_value = ""
        # response.headers may be email.message.Message; get_all handles repeated headers.
        for set_cookie in response.headers.get_all("Set-Cookie") or []:
            m = _NAGFORM_COOKIE_RE.search(set_cookie)
            if m:
                cookie_value = m.group(1)
                break

        token_match = _NAGFORM_INPUT_RE.search(body)
        token = token_match.group(1) if token_match else ""

        if self.verbose >= 3:
            print(f"DEBUG: CSRF cookie={'<got>' if cookie_value else '<missing>'} "
                  f"token={'<got>' if token else '<missing>'}")

        return cookie_value, token

    def _post(self, endpoint: str, data: dict[str, str], csrf_cookie: str = "") -> str:
        """Make HTTP POST request to Nagios API.

        Args:
            endpoint: API endpoint (e.g., 'cmd.cgi')
            data: POST data
            csrf_cookie: optional NagFormId cookie value to send alongside auth

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
        extra_cookies = {"NagFormId": csrf_cookie} if csrf_cookie else None
        self._apply_auth(request, extra_cookies=extra_cookies)

        try:
            response = opener.open(request, timeout=self.config.timeout)
            content: str = response.read().decode("utf-8")

            if self.verbose >= 3:
                print(f"DEBUG: Response: {content[:500]}")

            return content

        except urllib.error.HTTPError as e:
            raise NagiosAPIError(f"HTTP {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise NagiosAPIError(f"Connection error: {e.reason}") from e

    def _cmd_post(self, data: dict[str, str], preflight_params: dict[str, str]) -> str:
        """POST to cmd.cgi with the Nagios 4.4+ CSRF preflight.

        Issues a GET to seed the NagFormId cookie + read the hidden
        nagFormId field, then POSTs with both attached.
        """
        cookie_value, token = self._csrf_preflight(preflight_params)
        data_with_token = {**data, "nagFormId": token}
        return self._post("cmd.cgi", data_with_token, csrf_cookie=cookie_value)

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

    def get_problems(self) -> list[Service]:
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

    def get_all_hosts(self) -> list[Host]:
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

    def get_host_services(self, hostname: str) -> list[Service]:
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
        start_time = datetime.now().strftime(self.config.start_time_format)

        data = {
            "cmd_typ": "7",  # SCHEDULE_FORCED_SVC_CHECK
            "cmd_mod": "2",  # CMDMODE_COMMIT
            "host": hostname,
            "service": service,
            "start_time": start_time,
            "force_check": "on",
            "btnSubmit": "Commit",
        }
        preflight = {"cmd_typ": "7", "host": hostname, "service": service}

        content = self._cmd_post(data, preflight)

        return "successfully submitted" in content.lower()

    def force_host_check(self, hostname: str) -> bool:
        """Force immediate host check (runs the host's own check_command).

        Args:
            hostname: Host name

        Returns:
            True if command submitted successfully
        """
        start_time = datetime.now().strftime(self.config.start_time_format)

        # cmd_typ=96 is SCHEDULE_FORCED_HOST_CHECK on Nagios Core 4.x.
        # cmd_typ=17 reschedules every service of the host instead — exposed
        # as `force_host_services_check` below.
        data = {
            "cmd_typ": "96",  # SCHEDULE_FORCED_HOST_CHECK
            "cmd_mod": "2",  # CMDMODE_COMMIT
            "host": hostname,
            "start_time": start_time,
            "force_check": "on",
            "btnSubmit": "Commit",
        }
        preflight = {"cmd_typ": "96", "host": hostname}

        content = self._cmd_post(data, preflight)

        return "successfully submitted" in content.lower()

    def force_host_services_check(self, hostname: str) -> bool:
        """Force immediate check of every service of a host.

        Note: this does NOT run the host's own check_command — use
        ``force_host_check`` for that. cmd_typ=17 corresponds to
        SCHEDULE_FORCED_HOST_SVC_CHECKS on Nagios Core 4.x.

        Args:
            hostname: Host name

        Returns:
            True if command submitted successfully
        """
        start_time = datetime.now().strftime(self.config.start_time_format)

        data = {
            "cmd_typ": "17",  # SCHEDULE_FORCED_HOST_SVC_CHECKS
            "cmd_mod": "2",  # CMDMODE_COMMIT
            "host": hostname,
            "start_time": start_time,
            "force_check": "on",
            "btnSubmit": "Commit",
        }
        preflight = {"cmd_typ": "17", "host": hostname}

        content = self._cmd_post(data, preflight)

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
        preflight = {"cmd_typ": "34", "host": hostname, "service": service}

        content = self._cmd_post(data, preflight)

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
        preflight = {"cmd_typ": "33", "host": hostname}

        content = self._cmd_post(data, preflight)

        return "successfully submitted" in content.lower()

    def _parse_service(self, data: dict[str, Any]) -> Service:
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

    def _parse_host(self, data: dict[str, Any]) -> Host:
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
