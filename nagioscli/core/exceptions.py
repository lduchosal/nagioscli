"""Custom exceptions for nagioscli."""


class NagiosCliError(Exception):
    """Base exception for nagioscli."""

    pass


class ConfigurationError(NagiosCliError):
    """Raised when there's a configuration error."""

    pass


class AuthenticationError(NagiosCliError):
    """Raised when there's an authentication error."""

    pass


class NagiosAPIError(NagiosCliError):
    """Raised when there's an error with the Nagios API."""

    pass


class NotFoundError(NagiosCliError):
    """Raised when a host or service is not found."""

    pass


class CommandError(NagiosCliError):
    """Raised when a Nagios command fails."""

    pass
