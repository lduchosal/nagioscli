---
id: 601
title: "NAGIOSCLI / Upstream bug — cmd.cgi commands fail (missing CSRF + wrong date format)"
status: done
who: "Claude"
due_date: 
classified_at: 2026-05-31T20:58:59
classified_by: "key:c6597e8c-4d84-44f1-821e-8f9ad6720cf6"
section: core/client
section_title: "Core / client"
---

# #601 — NAGIOSCLI / Upstream bug — cmd.cgi commands fail (missing CSRF + wrong date format)

Bug report à transmettre upstream (https://github.com/lduchosal/nagioscli/issues).

---

## Title
cmd.cgi commands (check, check-host, ack, ack-host) silently fail on Nagios Core 4.4+ — missing CSRF token + hardcoded US date format

## Summary
All commands using cmd.cgi (force-check, ack) return 'Failed to submit' on Nagios Core 4.4+ because the CGI now requires a CSRF token, which nagioscli does not handle. Independently, the start_time is POSTed in US date format (MM-DD-YYYY), while many Nagios installs use European (DD-MM-YYYY) as their CGI date_format.

## Nagios behavior
Since Nagios Core 4.4 (CSRF protection enabled by default), cmd.cgi flow is:
1. GET cmd.cgi?cmd_typ=N&host=...&service=... — returns an HTML form, sets cookie 'NagFormId=<token>', includes hidden input 'nagFormId=<same token>'
2. POST cmd.cgi with the cookie + 'nagFormId=<token>' field — server validates cookie matches field; otherwise returns 'Error: Invalid or missing CSRF cookie!'

Current nagioscli skips step 1 entirely; POSTs without cookie or token; gets the CSRF error in the response body and falls back to 'Failed to submit'.

## Reproduction
    nagioscli check rs.example.com SOMESERVICE -vvv
    # DEBUG: POST .../cmd.cgi
    # DEBUG: Data: {'cmd_typ': '7', 'cmd_mod': '2', ...}
    # DEBUG: Response: <html>... <p>Error: Invalid or missing CSRF cookie!</p> ...
    # Failed to submit force check ...

Verified against Nagios Core 4.x. Manual curl reproducing the working flow:
    # GET to seed cookie + token
    curl -u USER:PASS -c jar -b jar \
      'https://nagios/cgi-bin/cmd.cgi?cmd_typ=7&host=H&service=S'
    # parse hidden <INPUT TYPE='hidden' NAME='nagFormId' VALUE='...'> from response
    # POST with cookie + token
    curl -u USER:PASS -c jar -b jar -X POST \
      -d 'cmd_typ=7&cmd_mod=2&nagFormId=...&host=H&service=S&start_time=...&btnSubmit=Commit' \
      'https://nagios/cgi-bin/cmd.cgi'

## Affected commands
- check (cmd_typ=7, SCHEDULE_FORCED_SVC_CHECK)
- check-host (cmd_typ=17, SCHEDULE_FORCED_HOST_CHECK)
- ack (cmd_typ=34, ACKNOWLEDGE_SVC_PROBLEM)
- ack-host (cmd_typ=33, ACKNOWLEDGE_HOST_PROBLEM)

Read-only statusjson.cgi commands (problems, status, hosts, services) are unaffected.

## Root cause
nagioscli/core/client.py:_post — builds POST directly, no GET preflight, no cookie jar.

## Fix proposal
1. In NagiosClient._post (or a wrapper applied to cmd_typ-bearing POSTs):
   - First do a GET on cmd.cgi with the same cmd_typ + host/service params
   - Capture Set-Cookie 'NagFormId' value
   - Parse hidden input nagFormId from the HTML body (regex on TYPE='hidden' NAME='nagFormId' VALUE='...')
   - POST with both the cookie AND the nagFormId field added to data
2. Add an integration test that mocks the GET preflight and asserts the POST contains the nagFormId field + matching cookie

## Date format issue (independent, smaller)
b29ed16 switched start_time to %m-%d-%Y, but Nagios accepts whatever its date_format directive declares. On installs using date_format=euro (DD-MM-YYYY), the current US format is rejected. Suggested approaches:
- Make the format configurable via [settings] in nagioscli.ini (e.g. start_time_format=%d-%m-%Y)
- Or auto-detect by parsing the start_time value from the GET preflight form (the same GET needed for CSRF already returns the server-formatted current time)

## Impact
Severity: high for any cmd.cgi consumer. Currently nagioscli ack/check/check-host/ack-host are no-ops on default Nagios installs, with the upside that the error is reported (vs silently swallowed by other tools).

## Discovery
While migrating 2113.ch monitoring scripts to nagioscli (ken #598). Confirmed via last_check timestamp before/after a force-check call: unchanged, proving the command never reached Nagios. Our own in-house nagios_force_check.py had the same bug, undetected because it didn't check the response body — nagioscli at least surfaces the failure clearly.

---

## Résolution

### Modifications
- nagioscli/core/client.py — added `_csrf_preflight(preflight_params)`: GETs cmd.cgi with the same `cmd_typ` + host/service params, captures `NagFormId` from `Set-Cookie`, and extracts the hidden `nagFormId` value from the HTML body. Two compiled regexes (`_NAGFORM_COOKIE_RE`, `_NAGFORM_INPUT_RE`) handle both single- and double-quoted Nagios markup.
- nagioscli/core/client.py — added `_cmd_post(data, preflight_params)`: thin wrapper that runs the preflight, appends `nagFormId=<token>` to the POST body, and forwards the `NagFormId` cookie to `_post`. The four cmd.cgi entrypoints (`force_service_check`, `force_host_check`, `acknowledge_service`, `acknowledge_host`) now route through it with the correct `cmd_typ`/host/service preflight scope.
- nagioscli/core/client.py — refactored `_post` to accept `csrf_cookie` and extracted auth/cookie composition into `_apply_auth`. Vouch and nginx-token auth paths now compose cookies cleanly with the CSRF cookie instead of overwriting each other.
- nagioscli/core/client.py — `start_time` for `force_service_check` / `force_host_check` now uses `self.config.start_time_format` instead of a hardcoded `%m-%d-%Y %H:%M:%S`. Default preserves the historical US format so no existing US deployment regresses.
- nagioscli/core/config.py — added `NagiosConfig.start_time_format: str = "%m-%d-%Y %H:%M:%S"` and wired `[settings] start_time_format` parsing.
- nagioscli.ini.example — documented `start_time_format` with the strftime patterns for the three Nagios `cgi.cfg date_format` values (us / euro / iso8601).
- doc/SPEC.md — added `start_time_format` to the example `[settings]` block.
- tests/unit/test_client_csrf.py (new) — 12 tests covering:
  - Regex correctness (`_NAGFORM_INPUT_RE`, `_NAGFORM_COOKIE_RE`) for both quote styles + Set-Cookie position variants.
  - All four cmd.cgi methods: assert exactly one GET preflight + one POST, correct `cmd_typ` in both, `nagFormId` field echoed in POST body, `NagFormId=<value>` in the request `Cookie` header alongside `Authorization: Basic`.
  - Missing-token degenerate case: POST still happens (with empty `nagFormId`, no Cookie) so the server's clear CSRF error reaches the user instead of a silent abort.
  - `start_time_format` round-trip for US / Euro / ISO patterns; default-value assertion.

### Comportements obtenus
- `nagioscli check`, `check-host`, `ack`, `ack-host` now succeed on Nagios Core 4.4+ default installs — every cmd.cgi POST carries a valid `nagFormId` + `NagFormId` cookie pair captured from a matching GET preflight.
- Operators on `date_format=euro` (`%d-%m-%Y`) or `iso8601` (`%Y-%m-%d`) installs can set `start_time_format` in `[settings]` instead of patching the source.
- Vouch and nginx-token auth users keep their existing cookies; the CSRF cookie is merged into the same `Cookie:` header rather than clobbering vouch.
- Read-only commands (statusjson.cgi) are unchanged — preflight only runs on cmd.cgi entrypoints.

### Garde-fous
- pytest: 43 passed (was 31) — 12 new tests in `tests/unit/test_client_csrf.py`, all pre-existing tests still green.
- ruff check (nagioscli + tests): clean (`All checks passed!`).
- mypy (nagioscli): clean (`Success: no issues found in 20 source files`).
- No public API or CLI signature changed; only additive (`start_time_format` config field defaults to historical behavior).
---

[← retour à core/client](index.md) · [voir log](../../log.md)
