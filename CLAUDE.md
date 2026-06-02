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
```

`ARCHITECTURE.md` is the source of truth for `ken wiki sync` section
paths — keep its YAML frontmatter in sync if you add/rename top-level
packages.

## Quality gate

`./publish.sh` is the full quality gate. It runs, in order:

1. `pdm run clean`
2. `pdm run install` + `install-dev`
3. `pdm run lint`
4. `pdm run typecheck`
5. `pdm run test-quick`
6. `pdm run version-patch` (bumps `nagioscli/__init__.py`)
7. `pdm build`
8. `pdm publish`

So running it both validates and ships a patch release — don't invoke
it casually. For local iteration without bumping/publishing, run the
gate steps directly: `pdm run lint && pdm run typecheck && pdm run test-quick`.

mypy is strict (`disallow_untyped_defs`, `warn_unreachable`, etc.) —
type new defs fully.

## Versioning

- Version lives in `nagioscli/__init__.py` (`__version__`).
- `publish.sh` bumps it via `pdm run version-patch` on every run. For
  minor/major bumps, run `pdm run version-minor` / `version-major`
  before `publish.sh` (or edit the script for that release).

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
