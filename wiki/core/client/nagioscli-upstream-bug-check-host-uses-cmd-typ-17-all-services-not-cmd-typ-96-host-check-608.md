---
id: 608
title: "NAGIOSCLI / Upstream bug — check-host uses cmd_typ=17 (= all services), not cmd_typ=96 (= host check)"
status: done
who: "Claude"
due_date: 
classified_at: 2026-05-31T21:36:53
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: core/client
section_title: "Core / client"
---

# #608 — NAGIOSCLI / Upstream bug — check-host uses cmd_typ=17 (= all services), not cmd_typ=96 (= host check)

Bug report à transmettre upstream (https://github.com/lduchosal/nagioscli/issues).

---

## Title
check-host uses cmd_typ=17 (SCHEDULE_FORCED_HOST_SVC_CHECKS), should be cmd_typ=96 (SCHEDULE_FORCED_HOST_CHECK)

## Summary
nagioscli check-host POSTs cmd_typ=17 with comment 'SCHEDULE_FORCED_HOST_CHECK', but on Nagios Core cmd_typ=17 is 'Schedule a check of all services for a host' (SCHEDULE_HOST_SVC_CHECKS family). The real 'Schedule a forced host check' (SCHEDULE_FORCED_HOST_CHECK) is cmd_typ=96. Result: nagioscli check-host re-schedules every service of the host instead of running the host's own check_command (typically the PING/check-host-alive). The host's last_check is never updated by this call.

## Reproduction
On any Nagios Core 4.x:

    nagioscli check-host SOMEHOST -vvv
    # DEBUG: POST .../cmd.cgi
    # DEBUG: Data: {'cmd_typ': '17', ...}
    # Force check submitted for host SOMEHOST     <-- claim
    
Then poll statusjson.cgi for that host:
    last_check unchanged
    
But every service of that host has its last_check advanced. So the command did run — it just isn't a host check.

## Authoritative source (form descriptions from Nagios CGI itself)
GET https://nagios/cgi-bin/cmd.cgi?cmd_typ=N&host=X (HTML form text):

| cmd_typ | Form description on Nagios Core 4.x                          |
|---------|--------------------------------------------------------------|
| 7       | 'Schedule a service check' (with force_check checkbox)       |
| 17      | 'Schedule a check of all services for a host'                |
| 33      | 'Acknowledge a host problem'                                 |
| 34      | 'Acknowledge a service problem'                              |
| 96      | 'Schedule a host check' (with force_check checkbox)          |

Cross-checked on a live install: cmd_typ=96 + force_check=on moves the host's last_check, cmd_typ=17 + force_check=on does not.

## Root cause
nagioscli/core/client.py force_host_check():

    data = {
        'cmd_typ': '17',  # SCHEDULE_FORCED_HOST_CHECK     <-- comment is wrong, value is wrong-for-intent
        ...
    }

The chosen cmd_typ matches SCHEDULE_HOST_SVC_CHECKS, not SCHEDULE_HOST_CHECK.

## Suggested fix
Three viable options, pick one:

1. **Fix the value** (smallest patch, matches the existing command name and docstring intent):
   - force_host_check(): change cmd_typ from '17' to '96', update comment to 'SCHEDULE_FORCED_HOST_CHECK'.

2. **Rename + add** (best UX, operators often want both):
   - Keep current behavior under a new name: check-host-services / check-all-services / 'force-check all services of host' (cmd_typ=17).
   - Add a new check-host that uses cmd_typ=96 (the actual host check). Update docstrings and tests.

3. **Document the discrepancy** (worst, but quick): rename force_host_check to force_host_services_check and update CLI command to check-host-services. Operators wanting a real host check would have to file an enhancement.

Recommendation: option 2. The 'force all services of a host' command is genuinely useful (it's what 2113.ch's existing monitor1 wrapper force-check-host.sh does via the named pipe), and the 'force host check' is what users naturally expect from a command literally called check-host.

## Tests
Adjust tests/unit/test_client_csrf.py and any related fixtures to assert cmd_typ for each entrypoint. If option 2, add round-trip tests for both new methods. Live regression idea: mock statusjson.cgi response to expose 'last_check' field and assert which timestamps advance after each call.

## Impact
Severity: medium. Users running 'nagioscli check-host X' currently get a different (still useful) action than the name implies. No false-success — the command does succeed and the lib correctly reports it. But operators debugging a host's check itself (e.g. PING flapping) get no help from this command, and the side-effect of rescheduling every service of a busy host can be surprising.

## Discovery
ken #606 — verifying the CSRF fix (f5f0d58 in 0.1.16). check (cmd_typ=7) verified working. check-host returned 'submitted' but host last_check did not advance over 30s. Inspected Nagios CGI HTML forms for cmd_typ=7/17/96 and confirmed cmd_typ=17 is 'all services of host', cmd_typ=96 is 'host check'. Compared to existing 2113.ch monitor1 wrapper force-check-host.sh which uses SCHEDULE_FORCED_HOST_SVC_CHECK (= cmd_typ=17 equivalent via named pipe) and is semantically the same as the lib's current behavior — confirming the lib's mis-name.

---

## Résolution

Option 2 retenue (rename + add) conformément à la recommandation du rapport.

### Modifications
- nagioscli/core/client.py — `force_host_check` change `cmd_typ` from `"17"` to `"96"` (SCHEDULE_FORCED_HOST_CHECK) in both the POST body and the CSRF preflight params. The docstring now says "runs the host's own check_command".
- nagioscli/core/client.py — new `force_host_services_check(hostname)` method using `cmd_typ="17"` (SCHEDULE_FORCED_HOST_SVC_CHECKS). Preserves the previous semantics of force-checking every service of a host under an honest name.
- nagioscli/cli/commands/check.py — new `nagioscli check-host-services <host>` CLI command wrapping `force_host_services_check`. Existing `nagioscli check-host` now performs the actual host check.
- tests/unit/test_client_csrf.py — renamed `test_force_host_check_uses_cmd_typ_17` → `test_force_host_check_uses_cmd_typ_96` and updated assertions (preflight URL + POST body now require `cmd_typ=96` and absence of `service` field). Added `test_force_host_services_check_uses_cmd_typ_17` for the new method, asserting the GET preflight + POST + cmd_typ=17 + nagFormId round-trip.
- tests/fixtures/mock_nagios_client.py — added `force_host_services_check` stub for parity with the real client interface.
- doc/SPEC.md — added a `check-host-services` row in the Action Commands table and clarified `check-host` (cmd_typ=96).
- **Bonus, discovered during live verification**: nagioscli/core/config.py — `configparser.ConfigParser()` was using default interpolation, so the `start_time_format` setting introduced in 0.1.16 raised `InterpolationSyntaxError: '%' must be followed by '%' or '('` on the first `%d` in any strftime pattern. Switched to `ConfigParser(interpolation=None)` and added regression test `TestLoadConfig::test_start_time_format_with_percent_loads`.

### Comportements obtenus
- `nagioscli check-host HOST` now runs the actual host check (cmd_typ=96). Verified live against www.monitor.2113.ch (host `2113.ch`):
  - Before: `last_check=2026-05-31 21:31:00`, `next_check=2028-07-05` (garbage — Nagios mis-parsed the US start_time on a euro server)
  - After (cmd_typ=96 + `start_time_format=%d-%m-%Y %H:%M:%S` in `[settings]`): `last_check=2026-05-31 21:34:47` (matches POST time), `next_check=2026-05-31 21:39:47` (normal 5-min interval).
- `nagioscli check-host-services HOST` exposes the previous behavior under its honest name.
- The `start_time_format` setting from 0.1.16 is actually usable now — strftime patterns with `%` no longer crash `load_config`.

### Garde-fous
- pytest: 45 passed (was 43) — 1 new test for `force_host_services_check`, 1 new regression test for ConfigParser interpolation, 1 existing test renamed/retargeted from cmd_typ=17 to cmd_typ=96.
- ruff check (nagioscli + tests): clean.
- mypy (nagioscli): clean.
- Live verification on www.monitor.2113.ch: `last_check` timestamp on host `2113.ch` advances by the expected amount after `nagioscli check-host`. The `check-host-services` mutating command was not exercised live to limit side effects; covered by mock test only.

### Note d'incompatibilité
`force_host_check` and `nagioscli check-host` now do something different from 0.1.16 (host's own check instead of all-services check). Operators wanting the old behavior switch to `check-host-services` / `force_host_services_check`. This is intentional per the bug report's option 2 recommendation — the previous semantics were a bug, the rename preserves the useful side-effect under its honest name.
---

[← retour à core/client](index.md) · [voir log](../../log.md)
