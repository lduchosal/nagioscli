---
id: 1239
title: "QUALITY / Ajoute deptry et pip-audit au publish.sh"
status: review
who: "Claude"
due_date: 
classified_at: 2026-11-25T23:18:47
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: packaging
section_title: "Packaging & tooling"
---

# #1239 — QUALITY / Ajoute deptry et pip-audit au publish.sh

## Contexte

`./publish.sh` (ken #998) couvre déjà format, lint, arch, typecheck,
interrogate, vulture, refurb, tests + coverage, et côté VS Code
`npm audit`. Il manque deux gates côté Python :

- **deptry** — cohérence entre les imports réels et les dépendances
  déclarées dans `pyproject.toml` (deps manquantes, inutilisées,
  transitives importées directement, deps dev utilisées au runtime).
- **pip-audit** — vulnérabilités connues (PyPI advisory / OSV) dans les
  dépendances installées, pendant Python de `npm audit`.

## À faire

- Ajouter `deptry` et `pip-audit` au groupe dev de `pyproject.toml`
  (+ `pdm lock`).
- Scripts PDM `deptry` et `pip-audit` (ou `audit`) dans
  `[tool.pdm.scripts]`.
- Config `[tool.deptry]` si nécessaire (ignores justifiés uniquement —
  le runtime est volontairement stdlib `urllib`, pas de `requests` /
  `httpx`).
- Étapes `print_step` + `run_command` (bloquantes) dans la phase
  quality de `publish.sh`, à côté de vulture / refurb et du
  `npm audit`.
- Ajouter les deux au composite `pdm run check`.
- Mettre à jour la liste des gates dans `CLAUDE.md` (section Quality
  gate) et la doc qualité (`doc/code-quality.md`) si pertinent.

## Critères d'acceptation

- `./publish.sh --quality` exécute deptry et pip-audit et échoue si
  l'un d'eux remonte un problème.
- `pdm run check` passe sur `main`.

---

## Résolution

### Modifications
- `pyproject.toml` : `deptry>=0.25` et `pip-audit>=2.9` dans le groupe dev ; scripts PDM `deptry` (`deptry .`) et `audit` ; tous deux ajoutés au composite `check`. Pas de `[tool.deptry]` : aucun ignore nécessaire.
- `publish.sh` : étapes bloquantes « Dependency Check (deptry) » et « Python Dependencies Security Audit (pip-audit) » après refurb, avant la suite de tests.
- **Plancher Python 3.10 → 3.11** (décision validée) : `requires-python`, classifiers, cibles black/ruff/mypy, matrice CI `python-package.yml`, `sonar.python.version`, `CLAUDE.md`.
- `CLAUDE.md` (section Quality gate) et `doc/code-quality.md` (nouvelle section « Gates de dépendances ») documentés.

### Comportements obtenus
- `pdm run audit` audite ce que **`pdm.lock`** épingle (tous les groupes : export `--without-hashes` + `pip-audit --no-deps --disable-pip`), pas la `.venv` — celle-ci contenait des paquets étrangers au projet (sqlparse, werkzeug, nagiosapi…) qui auraient généré des faux positifs.
- Fail-closed : l'export va dans un fichier `mktemp` chaîné en `&&`. Un pipe aurait été un fail-open (pdm.lock n'a pas de hashes → export avec hashes en erreur → liste vide → « No known vulnerabilities found », exit 0, constaté pendant l'implémentation). Vérifié : export cassé → rc=1.
- Premier run : 17 CVE sur `filelock 4.1.0` (outillage pdm/virtualenv). Toutes les versions corrigées (≥ 4.1.1) exigent Python ≥ 3.11 → plancher monté à 3.11 (3.10 EOL oct. 2026) ; lock résolu sur `filelock 4.3.1`, audit propre.
- deptry : aucune issue (runtime = click + certifi, urllib stdlib).

### Garde-fous
- `pdm run check` : passed (deptry, audit, 190 tests, metrics gate palier 1 PASS, vscode-check).
- `./publish.sh --quality` : **PASSED** (rc=0), toutes étapes vertes.
- `npm audit` de l'extension (échec pré-existant, 9 advisories dont 4 high) corrigé dans la foulée : `npm audit fix` (undici, markdown-it, @azure/msal-node, fast-uri, qs → `package-lock.json`) + `overrides` dans `vscode/package.json` (`glob ^14.0.6`, `minimatch ^11.0.9`) — même `@vscode/vsce` 4.1.1 reste dans la plage vulnérable via `minimatch ^10.2.6`. `npm audit` : 0 vulnerabilities ; `.vsix` de test identique (12 fichiers) à celui de la 0.1.28.
---

[← retour à packaging](index.md) · [voir log](../log.md)
