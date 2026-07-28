---
id: 821
title: "CLI / check-problems force-check tous les services en erreur"
status: done
who: "Claude"
due_date: 
classified_at: 2026-06-11T09:38:30
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: cli/commands
section_title: "CLI commands"
---

# #821 — CLI / check-problems force-check tous les services en erreur

## Contexte

Dans Nagios, beaucoup de services PKGVULN sont en CRITICAL. Relancer un
force check service par service (`nagioscli check <host> <service>`)
est fastidieux quand des dizaines d'hôtes sont concernés.

## Demande

Une commande qui force-check **tous** les services en erreur
(CRITICAL, WARNING ou UNKNOWN) **sans spécifier de host**, avec un
filtre optionnel sur le nom du service (ex. `PKGVULN`).

## Comportement attendu

- `nagioscli check-problems` — force check de tous les services en erreur.
- `nagioscli check-problems PKGVULN` — idem, limité aux services dont la
  description est `PKGVULN` (insensible à la casse).
- Affiche chaque soumission (succès/échec) et un résumé, exit code 1 si
  au moins une soumission a échoué.

## Definition of Done

- Commande `check-problems` enregistrée dans le CLI.
- Réutilise `get_problems()` + `force_service_check()` du client core.
- Tests unitaires (filtre, sans filtre, aucun problème, échec partiel).
- `pdm run lint && pdm run typecheck && pdm run test-quick` passent.

---

## Résolution

### Modifications
- nagioscli/cli/commands/check.py : nouvelle commande `check-problems [SERVICE]` —
  récupère les services en erreur via `client.get_problems()` (warning/critical/unknown)
  puis soumet `client.force_service_check()` pour chacun. Filtre optionnel sur la
  description exacte du service, insensible à la casse.
- tests/unit/test_cli_commands.py : classe `TestCheckProblems` (7 tests — sans filtre,
  filtre insensible à la casse, aucun problème, aucun match du filtre, échec partiel,
  erreur API par service, erreur API sur get_problems).
- README.md : exemple `check-problems PKGVULN` + lignes `check-host-services` et
  `check-problems` dans le tableau des commandes.

### Comportements obtenus
- `nagioscli check-problems` force-check tous les services en erreur, tous hôtes confondus.
- `nagioscli check-problems PKGVULN` limite aux services `PKGVULN` (casse ignorée).
- Chaque soumission est affichée avec le statut du service (ex. `(CRITICAL)`),
  suivi d'un résumé `Submitted N/M force check(s)`.
- Une `NagiosAPIError` sur un service n'interrompt pas le lot (le détail est
  visible en `-v`) ; exit code 1 si au moins une soumission a échoué, 4 si la
  récupération de la liste échoue.

### Garde-fous
- `pdm run lint` : passed (ruff, all checks).
- `pdm run typecheck` : passed (mypy strict, 21 fichiers).
- `pdm run test-quick` : 160 passed.
- Commit 1137431 poussé sur main ; publié via ./publish.sh.
---

[← retour à cli/commands](index.md) · [voir log](../../log.md)
