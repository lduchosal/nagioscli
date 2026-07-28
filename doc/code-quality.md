# Code quality — critères, baseline et paliers

> Tâche fondatrice : ken #998 — import du pattern publish/qualité de
> semacli (ken #828) et kenboard (ken #783/#788/#835/#995). Objectif :
> des critères **mesurables et rejouables**, un gate **bloquant**, une
> progression **par paliers** et un **ratchet best-ever** qui interdit
> toute régression.

## Mesurer

```sh
pdm run metrics            # snapshot des critères (table)
pdm run metrics-record     # idem + append dans doc/quality-history.csv
pdm run metrics-gate       # gate bloquant : plafonds + ratchet, exit 1 si violation
```

Le script (`scripts/quality_metrics.py`) n'utilise que les outils déjà
installés dans la venv (ruff, mypy, vulture, refurb, interrogate, coverage) +
l'AST stdlib — zéro dépendance runtime ajoutée. `test_cov` lit le dernier run
de `pdm run test` (lancer avant pour une valeur fraîche).

L'historique vit dans [`quality-history.csv`](quality-history.csv) (une ligne
par snapshot, committée). Convention : enregistrer un snapshot à la fin de
chaque palier, au minimum à chaque release.

Le gate est exécuté par `pdm run check` **et** par `publish.sh` (juste après
la suite complète pour lire une couverture fraîche). `sh publish.sh --quality`
rejoue toute la chaîne qualité sans bump ni publication.

## Critères suivis

| Critère | Définition | Baseline (2026-07-28, v0.1.25, ken #998) | Direction |
|---|---|---:|---|
| `loc_src` | lignes totales `nagioscli/**/*.py` | 1 932 | informatif |
| `max_file_lines` | plus gros fichier | 588 (`core/client.py`) | ↓ → ≤ 300 |
| `files_over_500` | fichiers > 500 lignes | 1 (`core/client.py`) | ↓ → 0 |
| `files_over_300` | fichiers > 300 lignes | 1 | ↓ → 0 |
| `functions` | fonctions définies (AST) | 77 | informatif |
| `max_func_lines` | plus longue fonction | 146 | ↓ → ≤ 50 |
| `funcs_over_50` | fonctions > 50 lignes | 6 | ↓ → 0 |
| `c901_over_10` | complexité cyclomatique > 10 (ruff C901) | 2 | ↓ → 0 |
| `ruff_debt` | findings du jeu de règles ruff *non encore imposées* | 100 | ↓ → 0 |
| `ignored_debt` | dette complexité/signatures (C901, PLR0913, PLR0915 en `--isolated`) | 4 | ↓ → 0 |
| `mypy_errors` | erreurs mypy strict | 0 | = 0 (gate) |
| `vulture` | code mort (confiance ≥ 80, whitelist `vulture_whitelist.py`) | 0 | = 0 (gate) |
| `refurb` | findings refurb | 0 | = 0 (gate) |
| `docstring_cov` | couverture docstrings (interrogate) | 92.3 % | ↑ → ≥ 95 |
| `test_cov` | couverture de tests | 93.5 % | ↑ → ≥ 95 |
| `min_file_cov` | pire couverture par fichier | 72.2 % (`cli/decorators.py`) | ↑ → ≥ 75 |

Le jeu `ruff_debt` (constante `DEBT_SELECT` du script) au palier 1 :
`ANN401,BLE,DTZ,EM,FBT,PLR,PTH,TRY` — dominé par TRY ×27, EM ×24,
FBT001 ×15, BLE001 ×11, ANN401 ×9.
Verrouillées dès le palier 1 (déjà à zéro dans `nagioscli/`) : `G`, `SLF`,
`PLC0415`, `ARG`, `PERF`, `RUF` — actives dans `[tool.ruff.lint] select`,
tests exemptés (`per-file-ignores`).

**Principe ratchet** : quand une famille du jeu `ruff_debt` tombe à zéro,
on l'ajoute au `[tool.ruff.lint] select` du gate pour verrouiller l'acquis,
et on la retire de `DEBT_SELECT`.

## Gate bloquant

`pdm run metrics-gate` échoue (exit 1) dès qu'une règle est violée. Trois
mécanismes complémentaires (mêmes verrous que semacli/kenboard) :

1. **Verrous ruff** — chaque famille tombée à zéro est activée dans
   `[tool.ruff.lint] select` : échec dès `pdm run lint`.
2. **Cibles par paliers** (`GATE_MAX`/`GATE_MIN` du script) — le palier
   courant est `GATE_PALIER` dans `scripts/quality_metrics.py`.
3. **Ratchet best-ever** (vs `quality-history.csv`) — aucun compteur
   (`files_over_300`, `funcs_over_50`, `c901_over_10`, `ruff_debt`,
   `ignored_debt`) ne peut dépasser son meilleur niveau historique, et
   `test_cov` ne peut pas tomber plus de 0,5 pt sous son record.

### Paliers

| Palier | `max_file` | `max_func` | `ruff_debt` | `ignored_debt` | `docstr` | `test_cov` | `min_file_cov` | Chantier principal |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 — ✓ fait 2026-07-28 (ken #998) | ≤ 600 | ≤ 150 | ≤ 100 | ≤ 4 | ≥ 92 | ≥ 90 | ≥ 70 | outillage ; vulture/refurb → 0 ; G/SLF/PLC0415/ARG/PERF/RUF verrouillés |
| 2 | ≤ 500 | ≤ 80 | ≤ 60 | ≤ 4 | ≥ 93 | ≥ 92 | ≥ 72 | découpe de `core/client.py` (588 l.), funnel BLE/TRY |
| 3 | ≤ 400 | ≤ 60 | ≤ 25 | ≤ 2 | ≥ 94 | ≥ 93 | ≥ 74 | EM/FBT → 0 et verrouillés ; fonctions > 50 l. cassées |
| 4 | ≤ 300 | ≤ 50 | = 0 | = 0 | ≥ 95 | ≥ 95 | ≥ 75 | ANN401/PLR → 0 (noqa argumentés aux frontières JSON/click) — puis mode verrou |

(`mypy_errors`, `vulture`, `refurb` = 0 et `docstring_cov` ≥ palier courant
sont bloquants à tous les paliers ; `files_over_500` est plafonné à 1 au
palier 1 — la découpe de `core/client.py` est le chantier du palier 2 — puis
à 0. `[tool.interrogate] fail-under` suit le palier.)

### Procédure d'évolution des paliers

1. **Déclencheur** : `pdm run metrics-gate` passe au vert sur le palier
   courant.
2. **Verrouiller** : `pdm run metrics-record` + commit du CSV (le ratchet
   fige le niveau atteint), puis `sh publish.sh` (release).
3. **Resserrer** : éditer `GATE_PALIER`/`GATE_MAX`/`GATE_MIN` dans
   `scripts/quality_metrics.py` selon le tableau ; activer dans
   `[tool.ruff.lint] select` les familles tombées à zéro et les retirer de
   `DEBT_SELECT` ; aligner `[tool.interrogate] fail-under`.
4. **Ouvrir le chantier** : créer la carte ken « QUALITY / Palier N » avec
   la sortie rouge de `metrics-gate` comme liste de travail.
5. **Dernier palier atteint** : le gate reste en place en mode verrou
   (cibles + ratchet) ; toute évolution ultérieure suit la même procédure.

Règle d'or : on ne **détend jamais** un seuil sans décision humaine
explicite, tracée dans une carte ken et dans l'historique du CSV.

## Hors périmètre local

- **Duplication** : suivie par SonarCloud (`lduchosal_nagioscli`), bloquée
  au publish par `pdm run sonar-gate` (`scripts/sonar_gate.py`).
- **Architecture** : verrouillée séparément par import-linter
  (`pdm run arch`) — couches `cli → services → core`, commandes
  indépendantes entre elles.
