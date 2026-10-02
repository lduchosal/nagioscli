# nagioscli for VS Code

Nagios Core state in the VS Code sidebar, driven by the same
`nagioscli.ini` as the `nagioscli` CLI (ken #1132).

- **Host problems**: DOWN / UNREACHABLE hosts, unhandled first.
- **Service problems**: WARNING / CRITICAL / UNKNOWN services (the CLI's
  `nagioscli problems`), unhandled first, then worst state. A badge on the
  view counts the problems nobody has acknowledged or put in downtime.
- **All hosts**: every monitored host; expand one to see its services.
- Each row shows the state, how long it has been in it, and the `ack`,
  `downtime`, `soft 1/3`, `checks off` markers; the tooltip carries the
  plugin output.
- **Status detail**: click a host or service to open a read-only document:
  state, attempts, last / next check, last change, then the plugin output,
  long output and performance data. It refreshes with the tree.
- **Force check now** (cmd.cgi 7 for a service, 96 for the host's own check)
  and **Acknowledge problem…** (sticky, notifies contacts, comment
  required — like `nagioscli ack`), inline or from the context menu.
  Commands go through the Nagios 4.4+ CSRF preflight like the CLI.
- **Open in Nagios**: the Nagios home, or the host / service page.

## Install

Each nagioscli release on GitHub attaches `nagioscli-vscode-<version>.vsix`:

```sh
gh release download v<version> -R lduchosal/nagioscli -p '*.vsix'
code --install-extension nagioscli-vscode-<version>.vsix
```

(or VS Code → Extensions → `…` → *Install from VSIX…*). No Marketplace.

## Configuration

Nothing to configure in VS Code: the extension reads `nagioscli.ini` like
`nagioscli` does.

| Search order | |
|---|---|
| `nagioscli.ini` | in the workspace folder, then each parent folder |
| `~/.nagioscli.ini` | |
| `/usr/local/etc/nagioscli.ini` | |

- `[nagios] url`, `username` (required).
- `[auth] method = password | pass_path | env_var | vouch_cookie |
  nginx_token`, or `[nagios] password` without `[auth]`. `pass_path` runs
  `pass <path>` once per configuration (the result is kept in memory, never
  written). The Vouch token saved by `nagioscli login`
  (`~/.nagioscli_token`) is used like the CLI does.
- `[settings] timeout`, `verify_ssl` (default `false`, as in the CLI:
  self-signed Nagios certificates are the common case),
  `start_time_format` (must match `date_format` in the server's `cgi.cfg`).

The ini is re-read on every refresh, so edits apply without reloading.

| Setting | Default | |
|---|---|---|
| `nagioscli.autoRefreshSeconds` | `60` | refresh period, `0` disables it; skipped while VS Code is in the background |
| `nagioscli.hideHandled` | `false` | hide acknowledged / downtime problems from the problem groups |

## Development

```sh
npm ci
npm run check      # biome lint + format, tsc --noEmit (JSDoc types), node --test with coverage gate
npm run package    # nagioscli-vscode-<version>.vsix
```

Plain JavaScript with `// @ts-check` + JSDoc, no build step, no runtime
dependency. `src/config.js`, `src/encoding.js`, `src/api.js` and
`src/status.js` do not import `vscode`. `src/extension.js` is tested
against `test/vscode-stub.js`.
