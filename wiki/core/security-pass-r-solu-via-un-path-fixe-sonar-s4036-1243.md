---
id: 1243
title: "SECURITY / pass résolu via un PATH fixe - Sonar S4036"
status: review
who: "Claude"
due_date: 
classified_at: 2026-11-25T23:42:08
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: core
section_title: "Core"
---

# #1243 — SECURITY / pass résolu via un PATH fixe - Sonar S4036

## Contexte

Le gate SonarCloud bloque la release (`new_security_rating` = 2, seuil 1) sur une vulnérabilité `javascript:S4036` — `vscode/src/config.js` : `execFile('pass', …)` résout le binaire `pass` via le `PATH` de l'utilisateur ; un répertoire inscriptible dans le `PATH` permet de substituer un faux `pass` qui reçoit la demande de mot de passe. Même schéma côté CLI (`core/auth.py`, `subprocess.run(["pass", …])`, `python:S4036`).

## À faire

- Résoudre `pass` uniquement dans une liste fixe de répertoires système et l'exécuter par chemin absolu, côté Python et côté extension (parité CLAUDE.md).
- Tests des deux côtés (trouvé / introuvable / non exécutable), gate de couverture VS Code inclus.
- Débloquer le gate SonarCloud de `publish.sh`.

---

## Résolution

### Modifications
- `nagioscli/core/auth.py` : `PASS_SEARCH_DIRS` (`/usr/bin`, `/bin`, `/usr/local/bin`, `/opt/homebrew/bin`, `/opt/local/bin`, `/run/current-system/sw/bin`) + `_find_pass()` (`shutil.which` restreint à ces dossiers) ; `pass` exécuté par chemin absolu ; introuvable → `AuthenticationError("'pass' command not found in <dirs>. Install password-store.")` avant tout `subprocess.run`.
- `vscode/src/config.js` : portage à l'identique — `PASS_SEARCH_DIRS` (gelé), `findPass(dirs)` (premier fichier régulier exécutable, dans l'ordre), `readPass(passPath, dirs = PASS_SEARCH_DIRS)` ; la branche ENOENT du callback disparaît (introuvable traité en amont).
- Tests : `tests/unit/test_auth.py` (fixture autouse `_find_pass` → `/usr/bin/pass`, classe `TestFindPass`) ; `vscode/test/config.test.js` (fake `pass` passé via `dirs` au lieu du `PATH`, PATH utilisateur ignoré, non exécutable / répertoire ignorés).
- Commit `d032033`.

### Comportements obtenus
- `pass` n'est plus jamais résolu via le `PATH` de l'utilisateur, côté CLI comme côté extension (parité CLAUDE.md).
- L'environnement de `pass` lui-même (gpg, getopt…) est inchangé : pas de régression pour les installations standard (Homebrew Apple Silicon / Intel, MacPorts, distro Linux, NixOS).
- Limite assumée : un `pass` installé hors de ces dossiers (`~/.local/bin`, profil nix utilisateur) n'est plus trouvé — message explicite listant les dossiers cherchés.

### Garde-fous
- `./publish.sh --quality` : PASSED (rc=0) — 196 tests, extension 100 % lignes (config.js 98.98 % branches), metrics gate palier 1 PASS (`ruff_debt` 100, message extrait en variable pour éviter EM102/TRY003).
- Gate SonarCloud : revérifié par le `./publish.sh` de release relancé après ce commit.
---

[← retour à core](index.md) · [voir log](../log.md)
