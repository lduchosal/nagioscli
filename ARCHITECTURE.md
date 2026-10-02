---
wiki:
  sections:
    - id: cli
      title: CLI layer
      description: Click entrypoint, shared decorators, error handlers, output formatting.
    - id: cli/commands
      title: CLI commands
      description: Individual click subcommands (problems, status, check, ack, hosts, services, login).
    - id: core
      title: Core
      description: Configuration loading, Nagios HTTP client, authentication, exceptions, and shared utilities.
    - id: core/models
      title: Core / models
      description: Data models and enums shared across the codebase — Service, Host, ServiceStatus, HostStatus, NagiosInfo.
    - id: core/client
      title: Core / client
      description: HTTP client for Nagios statusjson.cgi and cmd.cgi endpoints.
    - id: services
      title: Services
      description: Business services that compose the core client into higher-level operations (status, commands, info).
    - id: vscode
      title: VS Code extension
      description: vscode/ — sidebar of host/service problems and all hosts, status detail, force check, acknowledge; reads nagioscli.ini, shipped as a .vsix on the GitHub release.
    - id: tests
      title: Tests
      description: Unit tests, integration tests, fixtures, and mock client.
    - id: packaging
      title: Packaging & tooling
      description: pyproject.toml, pdm, publish script, CI, linters, type checking.
    - id: docs
      title: Documentation
      description: README, SPEC.md, and other user/developer-facing docs.
---

# nagioscli architecture

This document is the source of truth for how kenboard's `ken wiki sync`
maps tasks to a structured wiki tree. The YAML frontmatter above declares
the section paths; the prose below describes what lives in each section
so an LLM agent (or human) can classify a task with `ken wiki groom <id> <section>`.

The section paths mirror the real package layout under `nagioscli/`:

```
nagioscli/
├── cli/                    # section: cli
│   ├── commands/           # section: cli/commands
│   ├── decorators.py
│   └── handlers.py
├── core/                   # section: core
│   ├── client.py           # section: core/client
│   ├── models.py           # section: core/models
│   ├── config.py
│   ├── auth.py
│   ├── encoding.py
│   └── exceptions.py
└── services/               # section: services

vscode/                     # section: vscode — VS Code extension (ken #1132)
├── src/
│   ├── config.js           # nagioscli.ini + [auth] + pass, port of core/config.py + core/auth.py
│   ├── encoding.js         # UTF-8 / cp1252 tolerant decoding, port of core/encoding.py
│   ├── api.js              # statusjson.cgi + cmd.cgi with CSRF (node:https, no runtime deps)
│   ├── status.js           # pure presentation (states, ordering, labels, detail text)
│   └── extension.js        # VS Code glue (tree, status documents, commands)
└── test/                   # node --test, vscode-stub.js stands in for `vscode`
```

The extension is plain JavaScript with `// @ts-check` + JSDoc (no build
step) and has its own npm toolchain under `vscode/` (pattern semacli
ken #1131 / kenboard ken #1127). It never shells out to `nagioscli`: it
re-implements the config resolution of `core/config.py` / `core/auth.py`
and the cmd.cgi CSRF flow of `core/client.py` so the two read the same
`nagioscli.ini` the same way — **a change to the config format or to the
CGI protocol handling must land in both** (`vscode/src/*.js` and their
tests). `publish.sh` syncs `vscode/package.json` to the release version,
packages `nagioscli-vscode-<version>.vsix` before the PyPI upload, then
attaches it to the `v<version>` GitHub release.

Cross-cutting concerns map to:

- `tests` — anything under `tests/` (unit, integration, fixtures, mocks).
- `packaging` — `pyproject.toml`, `pdm.lock`, `publish.sh`, CI workflows
  (the `.vsix` release plumbing included; the extension code itself is
  `vscode`).
- `docs` — `README.md`, `doc/SPEC.md`, this file.

When a task spans several files, classify it by the file where the
**root cause** lives, not the largest diff. For example, an enum value
bug fixed across `core/models.py`, `cli/handlers.py`, tests, and fixtures
belongs in `core/models` because that is where the canonical definition
lives — everything else is downstream of it.
