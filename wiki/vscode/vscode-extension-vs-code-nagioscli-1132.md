---
id: 1132
title: "VSCODE / Extension VS Code nagioscli"
status: done
who: "Claude"
due_date: 
classified_at: 2026-10-02T18:58:31
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: vscode
section_title: "VS Code extension"
---

# #1132 — VSCODE / Extension VS Code nagioscli

**TL;DR** — nagioscli n'avait pas d'extension VS Code comme semacli/kenboard → extension `vscode/` (problèmes hôtes/services, tous les hôtes, détail, force check, acknowledge) lisant `nagioscli.ini`, même gate qualité que semacli #1131, `.vsix` packagé avant PyPI et attaché à la release GitHub `v<version>` par `publish.sh`.

semacli et kenboard se sont dotés d'une extension VSCode, j'en veux une pour nagioscli aussi. Regarde le travail qui a été effectué sur les répo ../semacli et ../kenboard et reprend le concept complet de l'extension, la publication dans les artefact de la release, la qualité, les tests unitaires, l'intégration dans le publish.sh etc.. n'oublie rien, analyse les diff des repos pour ne rien oublier.

---

## Résolution

Sources analysées : semacli e2fe9f8 / 3f788ac / 879de37 (ken #1131), kenboard 595cb1c / 4c8e343 / adb0c93 / 1e718d6 / f7040f5 (ken #1127, #1130).

### Modifications
- `vscode/src/config.js` : port de `core/config.py` + `core/auth.py` — recherche `nagioscli.ini` (workspace et parents, `~/.nagioscli.ini`, `/usr/local/etc`), `[auth]` password / pass_path (`pass`, résolu une fois par config) / env_var / vouch_cookie / nginx_token, token Vouch de `nagioscli login`, `[settings]` timeout / verify_ssl (défaut false comme la CLI) / start_time_format.
- `vscode/src/encoding.js` : port de `core/encoding.py` (UTF-8 + repli cp1252, ken #1104).
- `vscode/src/api.js` : statusjson.cgi (details=true) + cmd.cgi avec préflight CSRF Nagios 4.4+ (force check 7/96, ack 33/34 sticky + notification), node:https sans dépendance runtime, 401 => re-résolution des credentials.
- `vscode/src/status.js` : présentation pure (états, tri non-traité > sévérité > nom, durées, marqueurs ack/downtime/soft/checks off, texte du détail).
- `vscode/src/extension.js` : vue `nagioscli.status` (Host problems / Service problems / All hosts dépliables), badge des problèmes non traités, documents `nagioscli-status:` rafraîchis, commandes refresh / openNagios / showStatus / openInNagios / forceCheck / acknowledge, auto-refresh 60 s (fenêtre focus), `nagioscli.hideHandled`.
- `vscode/test/*` : 71 tests node --test + stub `vscode`; `package.json`, `biome.json`, `jsconfig.json`, `.vscodeignore`, `.gitignore`, icônes svg/png, README.
- `pyproject.toml` : `vscode-install/audit/lint/typecheck/test/package/check`, `vscode-check` dans `check`, `test-publish` (sortie compacte).
- `publish.sh` : bloc `{ … }`, 3 étapes extension (npm ci, npm audit, biome+tsc+tests), sync de version vers `vscode/package.json`, packaging `.vsix` avant PyPI (vérifie le nom versionné), release GitHub `v<version>` avec le `.vsix` (idempotente, commande de reprise), compteurs 18 / 29.
- CI : job `vscode` (lcov -> SonarCloud), `python-publish.yml` en `--skip-existing`.
- `sonar-project.properties` : `vscode/src` + `vscode/test`, lcov, suppression ciblée S4830 sur `api.js` (opt-in verify_ssl=false).
- `tests/unit/test_vscode_extension.py` : invariants du manifeste (version = `__version__`, une seule clé version, commandes enregistrées, menus valides, pas de dépendance runtime, icône, `.vscodeignore`).
- Docs : README, ARCHITECTURE.md (section `vscode`), CLAUDE.md.

### Comportements obtenus
- `npm run package` produit `nagioscli-vscode-<version>.vsix` (11 fichiers : src, media, package.json, README, LICENSE).
- Sans `nagioscli.ini` / serveur injoignable : message dans l'arbre, aucun crash.

### Garde-fous
- `./publish.sh --quality` : 18/18 vert (190 tests Python, metrics gate).
- Extension : biome 0, tsc strict 0, 71/71 tests, couverture 100 % lignes / 98.9 % branches / 99.2 % fonctions, npm audit 0 vulnérabilité.
- sdist : n'embarque que `tests/unit/test_vscode_extension.py` (skippé sans `vscode/`).
---

[← retour à vscode](index.md) · [voir log](../log.md)
