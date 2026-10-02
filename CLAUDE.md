# nagioscli — agent notes

CLI for managing Nagios Core via HTTP. Python 3.10+, packaged with PDM.

## Naming quirk

- **Repo / module / CLI binary:** `nagioscli`
- **PyPI distribution:** `nachos` (`pip install nachos`)

Don't "fix" mismatches between these — they are intentional.

## Layout

```
nagioscli/
├── cli/                # Click entrypoint, decorators, handlers
│   └── commands/       # One file per subcommand
├── core/               # client, config, auth, models, exceptions
└── services/           # higher-level ops composed from core
tests/{unit,integration,fixtures}
vscode/                 # VS Code extension (JS + JSDoc, own npm toolchain)
```

The VS Code extension (`vscode/`, ken #1132, pattern semacli ken #1131)
re-implements the config resolution and the cmd.cgi CSRF flow in JS
(`vscode/src/config.js`, `api.js`): any change to the `nagioscli.ini`
format (`core/config.py`, `core/auth.py`) or to the CGI handling
(`core/client.py`, `core/encoding.py`) must be ported there, tests
included. `pdm run vscode-install` (npm ci) then `pdm run vscode-check`
(biome + tsc --noEmit + node --test with a 100% lines / 95% branches
coverage gate) — also part of `pdm run check`.

`ARCHITECTURE.md` is the source of truth for `ken wiki sync` section
paths — keep its YAML frontmatter in sync if you add/rename top-level
packages.

## Quality gate

`./publish.sh` is the full quality gate (pattern imported from
semacli/kenboard, ken #998). Quality phase: clean, lockfile sync,
install, outdated report, format (ruff), format-check (black), lint,
arch (import-linter), typecheck, interrogate, vulture, refurb, full
test suite with coverage, the VS Code extension gates (npm ci, npm
audit, biome, tsc, node --test), then the blocking metrics gate
(`scripts/quality_metrics.py` — ceilings + best-ever ratchet vs
`doc/quality-history.csv`, policy in `doc/code-quality.md`).
Publish phase: git push + SonarCloud gate (`scripts/sonar_gate.py`),
version bump (synced to `vscode/package.json`), build, `.vsix`
packaging, PyPI publish, wiki sync/build (non-fatal), release commit +
`v<version>` tag + push (non-fatal), then the GitHub release
`v<version>` carrying `nagioscli-vscode-<version>.vsix`.

- `./publish.sh --quality` runs ONLY the quality phase — no bump, no
  publish. Safe to run anytime; prefer it for validation.
- A bare `./publish.sh` ships a release — don't invoke it casually.
- `pdm run check` covers the same local gates (no sonar) for quick
  composite runs; `pdm run lint && pdm run typecheck && pdm run test-quick`
  remains the fastest iteration loop.
- `gh release create` lives only in `publish.sh` (after `pdm publish`):
  it fires `python-publish.yml`, whose `twine upload --skip-existing`
  is then a no-op. Don't add another one, and don't drop
  `--skip-existing`.

mypy is strict (`disallow_untyped_defs`, `warn_unreachable`, etc.) —
type new defs fully.

## Versioning

- Version lives in `nagioscli/__init__.py` (`__version__`).
- `publish.sh` bumps a patch by default; pass `--minor` / `--major`
  for bigger bumps (`--quality` skips the bump entirely).

## Task tracking — kenboard `ken`

This project tracks work on a kenboard board. Run `ken help` for the
full agent guide. Short version:

1. `ken list --who Claude --status todo` — pick a task, announce why.
2. `ken move <id> --to doing` before starting.
3. Implement + run `pdm run check`.
4. `ken update <id> --desc-file /tmp/ken-<id>.md` with original desc
   verbatim + **Résolution** block (Modifications / Comportements
   obtenus / Garde-fous). Never use `\n` inside `--desc "..."` — it
   stores the literal characters and corrupts markdown.
5. `ken move <id> --to review`, then `ken wiki groom <id> <section>`
   using the deepest matching path from `ARCHITECTURE.md`.
6. Leave `review → done` for the user.

Title format: `MODULE / Titre` (e.g. `BUG / ack-host crashes on 500`).
No `<` or `>` in titles.

## Things not to do

- Don't add `requests` / `httpx` as a runtime dep — `core/client.py`
  uses stdlib `urllib` on purpose.
- Don't commit `.ken` (gitignored, contains an API token, mode 0600).
- Don't mark tasks `done` yourself.
