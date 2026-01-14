# nagioscli Specification

A Python CLI tool to manage Nagios Core via HTTP REST API.

## Overview

nagioscli provides a command-line interface to interact with Nagios Core's JSON CGI API. It allows querying status, listing problems, forcing checks, and managing acknowledgements.

## Target Nagios API

- **Base URL**: `http://<nagios-host>/nagios/cgi-bin/`
- **Endpoints**:
  - `statusjson.cgi` - Query host/service status
  - `cmd.cgi` - Submit external commands (force check, acknowledge, etc.)

## Authentication

- HTTP Basic Auth
- Credentials stored in:
  - Config file (`nagioscli.ini`)
  - Environment variables
  - Password manager (`pass`) integration

## Commands

### Status Commands

| Command | Description |
|---------|-------------|
| `nagioscli problems` | List all services with warning/critical/unknown status |
| `nagioscli status service <host> <service>` | Query specific service status |
| `nagioscli status host <host>` | Query specific host status |
| `nagioscli status all` | Show overview of all hosts and services |

### Action Commands

| Command | Description |
|---------|-------------|
| `nagioscli check <host> <service>` | Force immediate service check |
| `nagioscli check-host <host>` | Force immediate host check |
| `nagioscli ack <host> <service> <comment>` | Acknowledge service problem |
| `nagioscli ack-host <host> <comment>` | Acknowledge host problem |
| `nagioscli downtime <host> <service> <duration> <comment>` | Schedule service downtime |

### Info Commands

| Command | Description |
|---------|-------------|
| `nagioscli hosts` | List all monitored hosts |
| `nagioscli services <host>` | List all services for a host |
| `nagioscli info` | Show Nagios server info |

## Output Formats

- **Default**: Human-readable text
- **--json**: Raw JSON output
- **--quiet**: Minimal output (exit codes only)
- **--verbose**: Detailed debug output

## Configuration File

```ini
[nagios]
url = http://monitor.1.2113.ch/nagios
username = claude

[auth]
# One of: password, pass_path, env_var
method = pass_path
pass_path = nagios/claude

[settings]
timeout = 30
verify_ssl = false
```

## Architecture

```
nagioscli/
├── cli/                    # Command-line interface (click)
│   ├── __init__.py        # Main CLI group
│   ├── commands/          # Individual commands
│   │   ├── problems.py    # List problems
│   │   ├── status.py      # Status queries
│   │   ├── check.py       # Force checks
│   │   ├── ack.py         # Acknowledgements
│   │   ├── downtime.py    # Downtime scheduling
│   │   ├── hosts.py       # List hosts
│   │   └── services.py    # List services
│   ├── decorators.py      # Common CLI options
│   └── handlers.py        # Error handlers
├── core/                   # Core business logic
│   ├── config.py          # Configuration handling
│   ├── auth.py            # Authentication
│   ├── client.py          # Nagios HTTP client
│   ├── exceptions.py      # Custom exceptions
│   └── models.py          # Data models
├── services/               # Business services
│   ├── status_service.py  # Status queries
│   ├── command_service.py # External commands
│   └── info_service.py    # Server info
└── tests/                  # Test suite
    ├── unit/
    ├── integration/
    └── fixtures/
```

## Dependencies

- `click>=8.0` - CLI framework
- `urllib3` or stdlib only - HTTP client (no requests dependency)

## Development Tools

- `pdm` - Package manager
- `pytest` - Testing
- `ruff` - Linting and formatting
- `mypy` - Type checking

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Authentication error |
| 4 | API error |
| 5 | Not found |

## Status Codes (Nagios)

### Service Status
- 2 = OK
- 4 = WARNING
- 8 = CRITICAL
- 16 = UNKNOWN

### Host Status
- 2 = UP
- 4 = DOWN
- 8 = UNREACHABLE

## Implementation Phases

### Phase 1 - Core
- [x] Project structure
- [ ] Configuration loading
- [ ] HTTP client with basic auth
- [ ] `problems` command
- [ ] `status service` command
- [ ] `status host` command
- [ ] `check` command (force check)

### Phase 2 - Extended Commands
- [ ] `hosts` command
- [ ] `services` command
- [ ] `ack` command
- [ ] `downtime` command

### Phase 3 - Polish
- [ ] Comprehensive tests
- [ ] GitHub Actions CI
- [ ] PyPI publishing
- [ ] Documentation

## References

- Nagios Core CGI JSON API
- check_msdefender project (architecture reference)
- monitor/claude/bin scripts (working implementations)
