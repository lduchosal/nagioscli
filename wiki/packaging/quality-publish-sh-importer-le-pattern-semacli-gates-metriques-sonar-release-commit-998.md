---
id: 998
title: "QUALITY / publish.sh — importer le pattern semacli (gates metriques + sonar + release commit)"
status: done
who: "Claude"
due_date: 
classified_at: 2026-07-28T08:15:41
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: packaging
section_title: "Packaging & tooling"
---

# #998 — QUALITY / publish.sh — importer le pattern semacli (gates metriques + sonar + release commit)

Comparer `/Users/q/Projects/2113.ch/semacli/publish.sh` au `publish.sh` de nagioscli et mettre le nôtre à niveau sur leur pattern, en important un maximum de qualité.

Écarts identifiés (semacli → nagioscli) :

- Tests : semacli exécute la suite complète avec couverture (`pdm run test`) + tests d'intégration en replay strict ; nagioscli n'exécute que `test-quick`.
- Gate métriques bloquant (`scripts/quality_metrics.py` : plafonds absolus + ratchet best-ever contre `doc/quality-history.csv`).
- Gate SonarCloud (`scripts/sonar_gate.py` : push puis attente de l'analyse de HEAD, blocage sur le quality gate live).
- Wiki sync/build kenboard en mode non-fatal (`run_command_soft`) après le publish PyPI.
- Commit + push git final des artefacts de release (bump de version, wiki), non-fatal.
- Numérotation d'étapes cohérente (celle de semacli a dérivé : 1/13, 6/14, 9/16).

À conserver côté nagioscli : l'étape lockfile (`pdm lock -G :all`) absente de semacli, et la règle « pas de requests/httpx en dépendance runtime » (sonar_gate.py de semacli est déjà urllib pur).

---

## Résolution

Périmètre élargi en cours de tâche (demande utilisateur) : `kenboard/publish.sh` a aussi été comparé — c'est l'ancêtre du pattern et il porte plus de qualité que semacli ; le meilleur des deux a été importé.

### Modifications

- publish.sh : réécriture complète. De kenboard : flags `--quality` (chaîne qualité seule, sans bump ni publish), `--major|--minor|--patch`, `--help` ; compteur d'étapes auto-incrémenté (fin de la numérotation dérivante) ; `eval` dans run_command ; étapes explicites format/interrogate/vulture/refurb ; clean final. De semacli : suite complète avec couverture, metrics-gate, push + sonar-gate, wiki sync/build non-fatals APRÈS le publish PyPI, commit de release non-fatal. Conservé de nagioscli : lockfile sync (`pdm lock -G :all`). Ajouté : tag `v<version>` + `git push --tags` (schéma des tags existants). Pipeline : 15 étapes en `--quality`, 24 en publish.
- scripts/quality_metrics.py : port du harnais semacli (ken semacli #828). SRC=nagioscli, `DEBT_SELECT=ANN401,BLE,DTZ,EM,FBT,PLR,PTH,TRY`, palier 1 calibré sur la baseline mesurée (voir Garde-fous). Branché dans `pdm run check` et publish.sh.
- scripts/sonar_gate.py : port de la version kenboard (ken kenboard #835/#995 — timeout souple + prolongation si CI GitHub ou file compute-engine active + cap dur `--max-wait 3600`). PROJECT_KEY=lduchosal_nagioscli ; SONAR_TOKEN rendu optionnel (projet public, APIs analyses/gate/issues répondent en anonyme — vérifié en live).
- pyproject.toml : deps dev + `import-linter`, `vulture`, `refurb` ; scripts `arch`, `vulture`, `refurb`, `metrics`, `metrics-record`, `metrics-gate`, `sonar-gate` ; ruff : verrouillage des familles déjà à zéro (`G,SLF,PLC0415,ARG,PERF,RUF`) avec tests exemptés (per-file-ignores) ; contrats import-linter (couches cli→services→core, commandes indépendantes — les deux KEPT du premier coup) ; `[tool.vulture]` ; `[tool.coverage.run] omit=__main__.py` (shim jamais importé, écrasait min_file_cov à 0) ; interrogate fail-under 0→92 ; **fix** : `check` était une liste nue (pdm l'interprétait comme une commande+args, « format-check does not exist », exit 0 silencieux) → forme `{composite = [...]}`.
- doc/code-quality.md : politique qualité adaptée (critères, baseline 2026-07-28 v0.1.25, paliers 1→4, procédure de resserrage).
- doc/quality-history.csv : snapshot baseline enregistré (ratchet armé).
- vulture_whitelist.py : créé (vide — zéro faux positif à ce jour).
- nagioscli/ + tests : mise à zéro vulture/refurb — `login.py` (contextlib.suppress), `problems.py` (truthiness), `client.py` (dict |), `config.py` (pathlib, tue aussi 2 PTH), `conftest.py` (_args/_kwargs) ; reformatage `ruff format` (black --check toujours vert).
- CLAUDE.md : section Quality gate et Versioning mises à jour (`--quality`, flags de bump, interdiction de `gh release create` — python-publish.yml publie sur PyPI à la publication d'une release GitHub, doublon garanti).

### Comportements obtenus

- `sh publish.sh --quality` : les 15 étapes qualité passent sans bump ni publication — le gate complet est enfin rejouable sans risque.
- `pdm run check` exécute réellement ses 8 étapes (avant : no-op silencieux) et finit vert : lint (familles verrouillées), black, mypy strict, 2 contrats d'architecture KEPT, vulture 0, refurb 0, 160 tests, metrics-gate PASS palier 1.
- `pdm run sonar-gate` : trouve l'analyse de HEAD en anonyme et valide le gate live (testé : PASSED sur cb5b1d8).
- Baseline mesurée : loc 1932, max_file 588 (core/client.py, chantier palier 2), ruff_debt 100, ignored_debt 4, mypy/vulture/refurb 0, docstrings 92.3 %, couverture 93.5 %, min_file 72.2 %.

### Garde-fous

- sh publish.sh --quality : 15/15 vert (inclut lint, typecheck, arch, interrogate, vulture, refurb, suite complète, metrics-gate).
- pdm run check : vert (composite réparé).
- pdm run metrics-gate : PASS palier 1 ; ratchet armé par doc/quality-history.csv.
- pdm run sonar-gate : PASSED en live, accès anonyme.
- Non importé, volontairement : `gh release create` (doublon PyPI via python-publish.yml), `pdm update` auto pendant le publish (un publish ne change pas silencieusement les versions verrouillées — `pdm outdated` en étape soft à la place), étape VCR replay (aucune cassette : tests/integration ne contient qu'un __init__.py), flag `--ci` (publish.sh n'est pas appelé par la CI ici).
---

[← retour à packaging](index.md) · [voir log](../log.md)
