---
id: 599
title: "NAGIOSCLI / Upstream bug — ServiceStatus CRITICAL/UNKNOWN inversés"
status: done
who: "Claude"
due_date: 
classified_at: 2026-05-31T19:13:17
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: core/models
section_title: "Core / models"
---

# #599 — NAGIOSCLI / Upstream bug — ServiceStatus CRITICAL/UNKNOWN inversés

Bug report à transmettre upstream (https://github.com/lduchosal/nagioscli/issues).

---

## Title
ServiceStatus CRITICAL and UNKNOWN enum values are swapped — all CRITICAL alerts mislabeled as UNKNOWN (and vice-versa)

## Summary
ServiceStatus enum in core/models.py has CRITICAL and UNKNOWN values inverted relative to the Nagios statusjson.cgi bitmap. As a result, every CRITICAL service is displayed as UNKNOWN, and every UNKNOWN service is displayed as CRITICAL — both in text and JSON output. HostStatus (UP/DOWN/UNREACHABLE) is correct.

## Nagios reference
Nagios statusjson.cgi service status bitmap (cgi/statusjson.c):
    PENDING  = 1
    OK       = 2
    WARNING  = 4
    UNKNOWN  = 8     (2 << 2)
    CRITICAL = 16    (2 << 3)

Confirmed against live Nagios Core 4.x. Easy to double-check via curl:
    curl -u nagiosadmin:PASS 'https://nagios/cgi-bin/statusjson.cgi?query=service&hostname=H&servicedescription=S'
A real CRITICAL service returns 'status': 16.

## Observed (nagioscli 0.1.14)
Live Nagios returns status=16 for a CRITICAL service. nagioscli displays:
    $ nagioscli problems
    UNKNOWN  2113.ch / IMAPD_LOGINFAILED       <-- actually CRITICAL upstream
    CRITICAL backup-01 / WATCHDOG              <-- actually UNKNOWN upstream

    $ nagioscli problems --json
    {"status": 16, "status_text": "UNKNOWN"}     <-- wrong, 16=CRITICAL
    {"status":  8, "status_text": "CRITICAL"}    <-- wrong, 8=UNKNOWN

## Root cause
Two source files have the mapping inverted:

1. nagioscli/core/models.py:13-14
       CRITICAL = 8     # should be 16
       UNKNOWN = 16     # should be 8

2. nagioscli/cli/handlers.py:62
       status_map = {2: "OK", 4: "WARNING", 8: "CRITICAL", 16: "UNKNOWN"}
       # should be: {2: "OK", 4: "WARNING", 8: "UNKNOWN", 16: "CRITICAL"}

Test fixtures and unit tests encode the same inversion, so the existing test suite passes against the wrong values:

3. tests/unit/test_models.py:106-107
       assert ServiceStatus.CRITICAL == 8   # should be 16
       assert ServiceStatus.UNKNOWN == 16   # should be 8

4. tests/fixtures/service_data.json
       {"status":  8, "plugin_output": "DISK CRITICAL ..."}  # should be 16
       {"status": 16, "plugin_output": "SMTP UNKNOWN ..."}   # should be 8

HostStatus (models.py:17-22) is correct: UP=2, DOWN=4, UNREACHABLE=8.

## Fix
Swap 8 <-> 16 in (1) and the labels in (2). Update fixtures and tests in (3) and (4) to match real Nagios bitmap. Add a regression test that asserts:
    ServiceStatus.UNKNOWN  == 8
    ServiceStatus.CRITICAL == 16
and ideally an integration-style assertion that status_text('status': 16) == 'CRITICAL'.

## Impact
Severity: high. Any operator triaging alerts via nagioscli sees the wrong severity label, which inverts the urgency of every problem. UNKNOWN (often a check-script bug) gets escalated as CRITICAL, while real CRITICAL alerts (service down) get de-prioritized as UNKNOWN.

## Discovery
Found while migrating 2113.ch monitoring scripts (scripts/nagios_problems.py et al.) to nagioscli. Cross-checked against existing in-house Python script that uses the documented Nagios bitmap (SERVICE_STATUS = {2:'OK', 4:'WARNING', 8:'UNKNOWN', 16:'CRITICAL'}); the in-house tool and the Nagios web UI agree, nagioscli disagrees.

---

## Résolution

### Modifications
- nagioscli/core/models.py:13-14 — swapped `CRITICAL = 8`/`UNKNOWN = 16` to `UNKNOWN = 8`/`CRITICAL = 16` to match the Nagios `statusjson.cgi` bitmap.
- nagioscli/cli/handlers.py:62 — `status_map` in `OutputFormatter.format_service_status` corrected to `{2: "OK", 4: "WARNING", 8: "UNKNOWN", 16: "CRITICAL"}`.
- tests/unit/test_models.py:106-107 — updated `TestServiceStatus.test_status_values` expectations to the corrected bitmap.
- tests/unit/test_models.py — added `TestServiceStatus.test_nagios_bitmap_regression` pinning the upstream Nagios bitmap (UNKNOWN=8, CRITICAL=16) and asserting `Service(status=16).status_text == "CRITICAL"` / `Service(status=8).status_text == "UNKNOWN"` so a future re-swap fails loudly.
- tests/fixtures/service_data.json — `db01.example.com/DISK` (DISK CRITICAL) bumped from `status: 8` to `status: 16`; `mail01.example.com/SMTP` (SMTP UNKNOWN) bumped from `status: 16` to `status: 8`. The fixture now matches what live Nagios returns.

### Comportements obtenus
- `nagioscli problems` (text + `--json`) now labels every alert with the same severity that Nagios reports upstream — CRITICAL stays CRITICAL, UNKNOWN stays UNKNOWN.
- `Service(status=16).status_text == "CRITICAL"` and `Service(status=8).status_text == "UNKNOWN"` (previously the opposite).
- `ServiceStatus.CRITICAL.value == 16` (`2 << 3`) and `ServiceStatus.UNKNOWN.value == 8` (`2 << 2`), aligned with `cgi/statusjson.c`.
- `is_problem` semantics are unchanged: any non-OK status is still a problem (the regression only affected the *label*, not the alerting boundary).

### Garde-fous
- pytest (tests/): 31 passed (was 30) — includes the new regression test and the four pre-existing `TestMockNagiosClient::test_get_service_status_*` cases which now validate against the corrected fixtures.
- ruff check (nagioscli + tests): clean (`All checks passed!`).
- mypy (nagioscli): clean (`Success: no issues found in 20 source files`).
- HostStatus left untouched — confirmed correct per the bug report and unchanged tests still pass.
---

[← retour à core/models](index.md) · [voir log](../../log.md)
