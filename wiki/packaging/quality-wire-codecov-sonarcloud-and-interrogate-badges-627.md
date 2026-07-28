---
id: 627
title: "QUALITY / Wire codecov, SonarCloud and interrogate badges"
status: done
who: "Claude"
due_date: 
classified_at: 2026-07-28T08:56:54
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: packaging
section_title: "Packaging & tooling"
---

# #627 — QUALITY / Wire codecov, SonarCloud and interrogate badges

Aligner les checks de qualité/sécurité du repo nagioscli sur ceux de kenboard.

## Changements

- README : remplacé les 2 badges existants par le set complet kenboard (15 badges) — PyPI, build/publish, codecov, interrogate, 8 metrics SonarCloud.
- `pyproject.toml` : ajout de `interrogate>=1.7.0` en dev-dep, config `[tool.interrogate]` (`fail-under=0`, `generate-badge=.`), nouveau script `test-cov-xml`.
- `interrogate_badge.svg` généré et committé (100% docstring coverage).
- `.github/workflows/python-package.yml` :
  - test step produit maintenant `coverage.xml`
  - upload codecov via `codecov/codecov-action@v5` (uniquement sur 3.13)
  - upload artefact `coverage-xml` pour le job Sonar
  - nouveau job `sonarcloud` (`SonarSource/sonarqube-scan-action@v6`) qui dépend de `build`
- `sonar-project.properties` créé (`projectKey=lduchosal_nagioscli`, `organization=lduchosal`).
- `.gitignore` : ajout de `coverage.xml`.

## Setup externe effectué

- Repo activé sur codecov.io, `CODECOV_TOKEN` ajouté aux secrets GitHub.
- Projet créé sur sonarcloud.io (`lduchosal_nagioscli`), `SONAR_TOKEN` ajouté aux secrets, **Automatic Analysis désactivée** (sinon conflit avec le scan CI).

## Résultat

CI verte sur tous les jobs (4× build, codecov upload, SonarCloud scan).
Commits : `bf0fdcd` (README badges), `95b7ccc` (CI wiring).
---

[← retour à packaging](index.md) · [voir log](../log.md)
