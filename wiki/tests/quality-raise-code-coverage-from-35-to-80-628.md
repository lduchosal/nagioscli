---
id: 628
title: "QUALITY / Raise code coverage from 35% to 80%+"
status: done
who: "Claude"
due_date: 
classified_at: 2026-07-28T08:56:55
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: tests
section_title: "Tests"
---

# #628 — QUALITY / Raise code coverage from 35% to 80%+

Code coverage actuelle : **34.75%** (voir https://app.codecov.io/gh/lduchosal/nagioscli).
Objectif : **> 80%**.

## Résolution

**Coverage : 35% → 92.49%** (132 tests, tous verts, exécution < 0.3s).
Gate `--cov-fail-under=80` ajouté pour éviter toute régression future.

### Fichiers ajoutés

- `tests/unit/conftest.py` — fixtures partagées (`runner`, `cli`, `mock_client`, `stub_config`) qui patchent `load_config` + `NagiosClient` dans chaque module de commande.
- `tests/unit/test_cli_commands.py` — 38 tests via `click.testing.CliRunner` couvrant chaque sous-commande (`ack`, `ack-host`, `check`, `check-host`, `check-host-services`, `hosts`, `services`, `problems`, `status service`, `status host`, `login`, `logout`) avec golden path + JSON + quiet + verbose + tous les codes de sortie d'erreur.
- `tests/unit/test_handlers.py` — 12 tests sur `handle_error` (mapping exit codes 1-5) et `OutputFormatter`.
- `tests/unit/test_auth.py` — 12 tests sur `get_credentials`, `load_cached_vouch_token`, `_get_password_from_pass` (toutes les branches : success, returncode non-zero, password vide, FileNotFoundError, TimeoutExpired, erreur inattendue).
- `tests/unit/test_client_getters.py` — 19 tests sur les getters JSON (`get_service_status`, `get_host_status`, `get_problems`, `get_all_hosts`, `get_host_services`) + sélection du header auth (basic / nginx_token / vouch_cookie) + gestion d'erreurs (`HTTPError`, `URLError`, `JSONDecodeError`).

### Coverage par module (final)

| Module | Avant | Après |
|---|---|---|
| `cli/commands/*` | 0% | 91–100% |
| `cli/handlers.py` | 0% | 100% |
| `cli/decorators.py` | 0% | 72% (helpers non utilisés par les commandes) |
| `core/auth.py` | 46% | 97% |
| `core/client.py` | 53% | 91% |
| `core/config.py` | 76% | 76% |
| **TOTAL** | **35%** | **92%** |

### Gate

`pyproject.toml` : `test-cov-xml = "... --cov-fail-under=80"` — toute PR qui descend sous 80% fera échouer le CI.

### Commits

- `bedd88d` — test: raise coverage from 35% to 92% and add 80% gate
- `a5cebeb` — test: fix import order in test_cli_commands

### CI

Build (4× Python versions), codecov upload, SonarCloud scan : tous verts.
---

[← retour à tests](index.md) · [voir log](../log.md)
