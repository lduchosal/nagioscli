---
id: 780
title: "NAGIOSCLI / status service: exposer long_plugin_output, perf_data, last_check, current_attempt (statusjson.cgi)"
status: done
who: "Claude"
due_date: 
classified_at: 2026-06-09T15:18:46
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: cli/commands
section_title: "CLI commands"
---

# #780 — NAGIOSCLI / status service: exposer long_plugin_output, perf_data, last_check, current_attempt (statusjson.cgi)

## Problème

`nagioscli status service <host> <svc> --json` ne ramène que ~7 champs synthétiques :

```json
{
  "host": "...", "service": "...",
  "status": 16, "status_text": "CRITICAL",
  "output": "DF CRITICAL - zroot/backup is 95.35 (outside range 0:95)",
  "checks_enabled": true, "notifications_enabled": true,
  "acknowledged": true, "downtime": false
}
```

Insuffisant pour faire un vrai triage depuis le laptop / un agent : il manque le détail multi-ligne du plugin, les perfdata, l'historique d'état, le compteur d'attempts (soft/hard), la santé du check lui-même.

## Source dispo (mais pas exposée)

`statusjson.cgi?query=service&hostname=…&servicedescription=…` retourne déjà `data.service` avec tout ce qu'il faut. Exemple `mail2/DISK` (warning courant) :

```json
{
  "plugin_output": "DF CRITICAL - zroot/backup is 95.35 (outside range 0:95)",
  "long_plugin_output": "critical: zroot/backup is 95.35 (outside range 0:95)\n",
  "perf_data": "'zmaildir/mailbox'=53.23;93;95;0 'zroot/ROOT/default'=89.39;93;95;0 'zroot/backup'=95.35;93;95;0 ...",
  "max_attempts": 6, "current_attempt": 6,
  "state_type": 1,
  "last_check": 1781010038000, "next_check": 1781010638000,
  "last_state_change": 1780990232000, "last_hard_state_change": 1780990232000,
  "last_time_ok": 1780558512000, "last_time_warning": 1780990232000, "last_time_critical": 1781010038000,
  "last_notification": 0, "current_notification_number": 21,
  "problem_has_been_acknowledged": true, "acknowledgement_type": 2,
  "execution_time": 2.06, "latency": 0.02,
  "scheduled_downtime_depth": 0,
  "checks_enabled": true, "notifications_enabled": true
}
```

Sans `perf_data`, le triage de `mail2/DISK` perd l'info-clé : c'est `zroot/backup=95.35` qui dépasse — les 13 autres datasets sont OK. Avec uniquement `output`, on doit ssh sur mail2 pour comprendre.

## Champs à ajouter dans `--json`

Pass-through (renommer en snake_case si on uniformise) :

- `long_plugin_output`
- `perf_data`
- `current_attempt` / `max_attempts` / `state_type` (soft vs hard)
- `last_check` / `next_check` / `last_state_change` / `last_hard_state_change`
- `last_time_ok` / `last_time_warning` / `last_time_critical` / `last_time_unknown`
- `last_notification` / `current_notification_number` / `acknowledgement_type`
- `execution_time` / `latency` / `scheduled_downtime_depth`

## Proposition d'API

Deux options :

1. **Pass-through par défaut** — `status service --json` retourne `data.service` brut (ou tout passé au through avec renommage cohérent). Simple, pas de breaking change pour les consommateurs qui lisent `.host`/`.status_text`/`.output`.
2. **Flag opt-in** — `nagioscli status service <h> <s> --detail` (ou `--full`) déclenche le pass-through complet. Préserve la sortie texte courte par défaut.

Pref perso : (1) avec un mapping explicite (clé renommée `plugin_output`→`output`, `problem_has_been_acknowledged`→`acknowledged`, etc.) pour garder la compat lecteurs existants tout en exposant tout le reste.

## Sortie texte (non-JSON)

La sortie texte courte peut rester telle quelle ; éventuellement ajouter `(soft|hard) attempt N/M` et une 2e ligne `long_plugin_output` quand non vide. Perfdata seulement avec `--perfdata` ou `--verbose`.

## Repo / refs

- Package PyPI : `nachos` (binaire `nagioscli`).
- Repo GitHub : https://github.com/lduchosal/nagioscli
- Précédents fix upstream : ken #599 (bitmap inversé), #601 (CSRF Nagios 4.4 cmd.cgi), #608 (`cmd_typ=96` pour host check).
- Méthode connue : équivalent curl déjà documenté dans `NAGIOS.md` § "Détail d'une alerte".

## DoD

- `nagioscli status service <h> <s> --json` expose au minimum : `long_plugin_output`, `perf_data`, `current_attempt`, `max_attempts`, `state_type`, `last_check`, `last_state_change`, `execution_time`, `latency`.
- Pas de régression pour les consommateurs lisant `output`/`status`/`status_text`/`acknowledged`.
- Bump version, PR upstream lduchosal/nagioscli, mention ken # dans CHANGELOG.

---

## Résolution

Approche **(1) pass-through avec mapping explicite** : tous les champs
du payload `data.service` sont remontés dans `--json`, avec les clés
historiques renommées préservées (`plugin_output`→`output`,
`problem_has_been_acknowledged`→`acknowledged`, etc.).

### Modifications

- `nagioscli/core/models.py` : `Service` dataclass étendu avec
  `long_plugin_output`, `perf_data` (déjà présent), `current_attempt`,
  `max_attempts`, `state_type`, `acknowledgement_type`,
  `scheduled_downtime_depth`, `last_check`, `next_check`,
  `last_state_change`, `last_hard_state_change`, `last_time_ok`,
  `last_time_warning`, `last_time_critical`, `last_time_unknown`,
  `last_notification`, `current_notification_number`,
  `execution_time`, `latency`.
  - Les anciens `last_check`/`last_state_change` typés
    `datetime | None` (jamais peuplés, jamais lus dans le code ni
    dans les tests) sont repurposed en `int` (ms epoch — c'est ce que
    renvoie Nagios), pour un pass-through honnête.
  - Idem côté `Host` pour cohérence (futur travail similaire).
- `nagioscli/core/client.py` : `_parse_service` populate l'ensemble des
  nouveaux champs depuis le payload API. Préserve la dérivation
  `scheduled_downtime = depth > 0` ET expose `scheduled_downtime_depth`.
- `nagioscli/cli/commands/status.py` :
  - `_emit_service_json` : passe tous les champs (mapping explicite,
    clés historiques inchangées).
  - `_emit_service_text` : ajoute `(soft|hard) attempt N/M` quand
    `max_attempts > 0`, et imprime `long_plugin_output` sur une 2e
    ligne quand non vide (perfdata laissé hors texte court).
- Tests :
  - `tests/unit/test_client_getters.py` :
    `test_parses_full_service_payload` — payload `mail2/DISK` complet,
    asserts sur les 14+ nouveaux champs.
  - `tests/unit/test_cli_commands.py` :
    `test_service_json_exposes_detail_fields` — vérifie présence des
    9 champs DoD + non-régression des clés `output`/`status_text`/
    `acknowledged`/`downtime`.
    `test_service_text_shows_attempt_and_long_output` — la ligne
    `soft attempt 3/6` et `long_plugin_output` apparaissent.

### Comportements obtenus

- `nagioscli status service mail2 DISK --json` retourne désormais
  29 clés (vs. 9 avant), permettant à `jq` / agent de récupérer
  `perf_data`, l'attempt soft/hard, les timestamps complets sans ssh.
- `nagioscli status service mail2 DISK` (texte) affiche
  `Status: WARNING (hard attempt 6/6)` puis la ligne
  `long_plugin_output` quand non vide.
- Pas de breaking change : les clés `host`, `service`, `status`,
  `status_text`, `output`, `checks_enabled`, `notifications_enabled`,
  `acknowledged`, `downtime` gardent exactement le même nom et la
  même sémantique.

### Garde-fous

- `pdm run lint` : All checks passed.
- `pdm run typecheck` : Success, no issues found in 21 source files
  (mypy strict, `disallow_untyped_defs`).
- `pdm run test-quick` : 153 tests OK (3 nouveaux).
- Couverture maintenue ≥ 80 % (gate `test-cov-xml --cov-fail-under=80`).
- Aucun ajout de dépendance runtime ; toujours stdlib `urllib`.

Version publiée : voir CHANGELOG / PyPI (bump effectué par `publish.sh`).
---

[← retour à cli/commands](index.md) · [voir log](../../log.md)
