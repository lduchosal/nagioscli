---
id: 781
title: "DOC / self-update déjà livré (voir #759)"
status: done
who: "Claude"
due_date: 
classified_at: 2026-06-09T15:33:00
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: cli/commands
section_title: "CLI commands"
---

# #781 — DOC / self-update déjà livré (voir #759)

## Demande

Réutiliser le modèle de `self-update` de `../kenboard` ou `../semacli`
pour exposer `nagioscli self-update`.

## Statut

**Déjà livré** — implémenté dans ken #759, publié dans nachos 0.1.21
(https://pypi.org/project/nachos/0.1.21/).

Modèle retenu : celui de `../semacli`
(`semacli/cli/commands/self_update.py`), plus riche que celui de
kenboard :

- Compare la version installée à la dernière release sur PyPI avant
  d'agir.
- Flags `--check`, `--pre`, `--dry-run`.
- Codes de sortie 0/1/2 (à jour-ou-OK / upgrade-dispo-ou-pip-échoué /
  PyPI-injoignable).
- `sys.executable -m pip install --upgrade nachos` pour cibler
  l'interpréteur courant.

Différences avec l'original semacli :

- Pas de dépendance `requests` (CLAUDE.md interdit `requests`/`httpx`
  en runtime). Utilise `urllib.request.urlopen` avec un contexte SSL
  monté sur `certifi.where()` pour éviter `CERTIFICATE_VERIFY_FAILED`
  sur macOS Python.
- Helpers internes identiques (`_fetch_latest_version`, `_is_stable`,
  `_version_key`, `_pip_command`).

## Référence

- Fichier : `nagioscli/cli/commands/self_update.py`
- Tests : `tests/unit/test_self_update.py` (18 tests, miroirs adaptés
  de `../semacli/tests/unit/test_self_update.py`)
- Enregistrement : `nagioscli/cli/commands/__init__.py` via
  `register_self_update_commands`
- Ken source : #759 (status `review`, classé `cli/commands`)
- Release : nachos 0.1.21

## Pas d'action requise

Cette tâche est purement un marqueur pour signaler le doublon de
demande — aucun code à modifier, aucun bump de version.
---

[← retour à cli/commands](index.md) · [voir log](../../log.md)
