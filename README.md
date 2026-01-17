# nagioscli

[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A CLI tool to manage Nagios Core via HTTP REST API.

## Features

- Query host and service status
- List all problems (warning, critical, unknown)
- Force immediate checks
- Acknowledge problems
- List hosts and services
- JSON output support
- Multiple authentication methods:
  - Basic auth (password, environment variable)
  - Password manager (`pass`) integration
  - Vouch Proxy (SSO/OAuth) support

## Installation

```bash
# From PyPI
pip install nachos

# From source
pip install git+https://github.com/lduchosal/nagioscli.git

# Development
git clone https://github.com/lduchosal/nagioscli.git
cd nagioscli
pdm install
```

## Quick Start

### Configuration

Create `nagioscli.ini` in the current directory or `~/.nagioscli.ini`:

```ini
[nagios]
url = http://nagios.example.com/nagios
username = nagiosadmin

[auth]
method = pass_path
pass_path = nagios/admin

[settings]
timeout = 30
```

### Basic Usage

```bash
# List all problems
nagioscli problems

# Query service status
nagioscli status service web01.example.com HTTP

# Query host status
nagioscli status host web01.example.com

# Force service check
nagioscli check web01.example.com HTTP

# Acknowledge a problem
nagioscli ack web01.example.com HTTP "Working on it"

# List all hosts
nagioscli hosts

# List services for a host
nagioscli services web01.example.com
```

## Commands

| Command | Description |
|---------|-------------|
| `problems` | List all services with problems |
| `status service <host> <service>` | Query service status |
| `status host <host>` | Query host status |
| `check <host> <service>` | Force service check |
| `check-host <host>` | Force host check |
| `ack <host> <service> <comment>` | Acknowledge service problem |
| `ack-host <host> <comment>` | Acknowledge host problem |
| `hosts` | List all monitored hosts |
| `services <host>` | List services for a host |
| `login` | Authenticate via Vouch Proxy (SSO) |
| `logout` | Clear saved authentication token |

## Output Options

```bash
# JSON output
nagioscli problems --json

# Quiet mode (exit codes only)
nagioscli problems --quiet

# Verbose debugging
nagioscli problems -v
nagioscli problems -vv
nagioscli problems -vvv
```

## Configuration Options

### Authentication Methods

nagioscli supports multiple authentication methods for different environments.

#### Basic Auth - Password in config file
```ini
[nagios]
url = http://nagios.example.com/nagios
username = admin
password = secret
```

#### Basic Auth - Password from pass (password-store)
```ini
[nagios]
url = http://nagios.example.com/nagios
username = admin

[auth]
method = pass_path
pass_path = nagios/admin
```

#### Basic Auth - Password from environment variable
```ini
[nagios]
url = http://nagios.example.com/nagios
username = admin

[auth]
method = env_var
env_var = NAGIOS_PASSWORD
```

#### Vouch Proxy (SSO/OAuth)

For Nagios behind [Vouch Proxy](https://github.com/vouch/vouch-proxy) with SSO authentication:

```bash
# Interactive login - opens browser, paste cookie from DevTools
nagioscli login
```

The token is cached in `~/.nagioscli_token` and used automatically.

Alternatively, set the cookie directly in config:
```ini
[nagios]
url = https://nagios.example.com/nagios
username = admin

[auth]
method = vouch_cookie
vouch_cookie = H4sIAAAA...
```

To get the cookie value manually:
1. Open browser to your Nagios URL
2. Authenticate via SSO
3. Open DevTools (F12) → Application → Cookies
4. Copy the `VouchCookie` value

To logout and clear the cached token:
```bash
nagioscli logout
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Authentication error |
| 4 | API error |
| 5 | Not found |

## Development

```bash
# Clone and setup
git clone https://github.com/lduchosal/nagioscli.git
cd nagioscli
pdm install -G dev

# Run tests
pdm test

# Lint and format
pdm lint
pdm format

# Type check
pdm typecheck

# Build
pdm build
```

## Architecture

```
nagioscli/
├── cli/                    # Click CLI interface
│   ├── commands/           # Individual commands
│   ├── decorators.py       # Common CLI options
│   └── handlers.py         # Error handlers
├── core/                   # Core business logic
│   ├── auth.py             # Authentication
│   ├── client.py           # Nagios HTTP client
│   ├── config.py           # Configuration
│   ├── exceptions.py       # Custom exceptions
│   └── models.py           # Data models
└── services/               # Business services
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Related Projects

- [check_msdefender](https://github.com/lduchosal/check_msdefender) - Nagios plugin for Microsoft Defender
