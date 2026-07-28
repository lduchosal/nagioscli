---
id: 630
title: "QUALITY / Fix SonarCloud issues (SSL annotations, constants, complexity)"
status: done
who: "Claude"
due_date: 
classified_at: 2026-06-02T08:29:17
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: core/client
section_title: "Core / client"
---

# #630 — QUALITY / Fix SonarCloud issues (SSL annotations, constants, complexity)

## Contexte

SonarCloud remontait 7 issues ouvertes sur le projet `lduchosal_nagioscli` :

- **python:S5527** (Vulnerability, HIGH) — `nagioscli/core/client.py:51` — *Enable server hostname verification on this SSL/TLS connection.*
- **python:S4830** (Vulnerability, HIGH) — `nagioscli/core/client.py:53` — *Enable server certificate validation on this SSL/TLS connection.*
- **python:S1192** ×3 (Code smell) — `nagioscli/core/client.py` lignes 265, 268, 427 — littéraux `"statusjson.cgi"`, `"Unknown error"`, `"successfully submitted"` dupliqués ≥5 fois.
- **python:S3776** (Code smell) — `nagioscli/cli/commands/problems.py:16` — complexité cognitive 17 (max 15).
- **python:S3776** (Code smell) — `nagioscli/cli/commands/status.py:15` — complexité cognitive 24 (max 15).

## Résolution

Commit `9b025b8` — *refactor: address SonarCloud issues (SSL annotations, constants, complexity)*.

### Modifications

- `nagioscli/core/client.py`
  - Ajout de constantes module-level : `_STATUS_JSON_CGI`, `_UNKNOWN_ERROR`, `_SUCCESS_MARKER` ; remplacement des 5+5+5 occurrences (S1192).
  - Annotation `# NOSONAR` sur `ssl_context.check_hostname = False` et `ssl_context.verify_mode = ssl.CERT_NONE` avec rationale : opt-in utilisateur explicite via `verify_ssl=False` (Nagios self-signed). Comportement runtime inchangé (S5527, S4830).
- `nagioscli/cli/commands/problems.py`
  - Extraction de `_emit_problems_json(services)` et `_emit_problems_text(services)` ; le corps de `problems_cmd` ne contient plus que le dispatch json/quiet/text (S3776).
- `nagioscli/cli/commands/status.py`
  - Extraction de `_emit_service_json/_text(svc)` et `_emit_host_json/_text(host)` ; `service_status_cmd` et `host_status_cmd` se réduisent au dispatch (S3776).

### Comportements obtenus

- Toutes les sorties CLI (`status service`, `status host`, `problems` — JSON, quiet, texte) sont byte-pour-byte identiques à avant.
- `verify_ssl=False` continue de désactiver la vérification du certificat ET du hostname comme avant (pas de durcissement silencieux du défaut).
- `pdm run lint` (ruff) ✓, `pdm run typecheck` (mypy strict) ✓, `pdm run test-quick` 45/45 ✓.

### Garde-fous

- `verify_ssl` reste à `False` par défaut dans `NagiosConfig` — durcir le défaut serait un breaking change pour les configs existantes qui n'ont pas la clé `verify_ssl` dans `[settings]`. À traiter dans une tâche dédiée si voulu.
- Les constantes sont préfixées `_` pour signaler qu'elles sont privées au module (pas une API publique).
- Les helpers `_emit_*` sont aussi privés au module — pas de dépendance externe à maintenir.
---

[← retour à core/client](index.md) · [voir log](../../log.md)
