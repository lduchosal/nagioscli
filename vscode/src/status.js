// @ts-check
// Pure status presentation: state names, problem filtering and ordering,
// tree labels and the text of the host / service detail document. Mirrors
// nagioscli/core/models.py. No `vscode` import.

/** SERVICE_* bitmasks of cgiutils.h (models.ServiceStatus). */
const SERVICE_STATES = { 1: 'PENDING', 2: 'OK', 4: 'WARNING', 8: 'UNKNOWN', 16: 'CRITICAL' };
/** HOST_* bitmasks of cgiutils.h (models.HostStatus). */
const HOST_STATES = { 1: 'PENDING', 2: 'UP', 4: 'DOWN', 8: 'UNREACHABLE' };

/** Problem ordering: worst first (CRITICAL, UNKNOWN, WARNING / DOWN, UNREACHABLE). */
const SERVICE_SEVERITY = { 16: 0, 8: 1, 4: 2 };
const HOST_SEVERITY = { 4: 0, 8: 1 };

/** Codicon + theme colour per state name. */
const STATE_ICONS = {
  OK: ['pass', 'testing.iconPassed'],
  UP: ['pass', 'testing.iconPassed'],
  WARNING: ['warning', 'list.warningForeground'],
  CRITICAL: ['error', 'testing.iconFailed'],
  DOWN: ['error', 'testing.iconFailed'],
  UNREACHABLE: ['debug-disconnect', 'testing.iconFailed'],
  UNKNOWN: ['question', 'charts.purple'],
  PENDING: ['clock', 'disabledForeground'],
};

/**
 * @typedef {import('./api').Service} Service
 * @typedef {import('./api').Host} Host
 */

/**
 * @param {number} status
 * @returns {string}
 */
function serviceState(status) {
  return (
    SERVICE_STATES[/** @type {keyof typeof SERVICE_STATES} */ (status)] ?? `UNKNOWN(${status})`
  );
}

/**
 * @param {number} status
 * @returns {string}
 */
function hostState(status) {
  return HOST_STATES[/** @type {keyof typeof HOST_STATES} */ (status)] ?? `UNKNOWN(${status})`;
}

/**
 * WARNING / CRITICAL / UNKNOWN (PENDING is not a problem, like the CLI).
 * @param {Service} svc
 * @returns {boolean}
 */
function isServiceProblem(svc) {
  return svc.status in SERVICE_SEVERITY;
}

/**
 * DOWN / UNREACHABLE.
 * @param {Host} host
 * @returns {boolean}
 */
function isHostProblem(host) {
  return host.status in HOST_SEVERITY;
}

/**
 * Acknowledged or in scheduled downtime: someone is already on it.
 * @param {Service | Host} row
 * @returns {boolean}
 */
function isHandled(row) {
  return Boolean(row.problem_has_been_acknowledged) || (row.scheduled_downtime_depth ?? 0) > 0;
}

/**
 * Unhandled first, then worst state, then host / service name.
 * @param {Service[]} services
 * @returns {Service[]}
 */
function sortServiceProblems(services) {
  const rank = (/** @type {Service} */ s) =>
    SERVICE_SEVERITY[/** @type {keyof typeof SERVICE_SEVERITY} */ (s.status)] ?? 9;
  return [...services].sort(
    (a, b) =>
      Number(isHandled(a)) - Number(isHandled(b)) ||
      rank(a) - rank(b) ||
      a.host_name.localeCompare(b.host_name) ||
      a.description.localeCompare(b.description),
  );
}

/**
 * Unhandled first, then DOWN before UNREACHABLE, then name.
 * @param {Host[]} hosts
 * @returns {Host[]}
 */
function sortHostProblems(hosts) {
  const rank = (/** @type {Host} */ h) =>
    HOST_SEVERITY[/** @type {keyof typeof HOST_SEVERITY} */ (h.status)] ?? 9;
  return [...hosts].sort(
    (a, b) =>
      Number(isHandled(a)) - Number(isHandled(b)) ||
      rank(a) - rank(b) ||
      a.name.localeCompare(b.name),
  );
}

/**
 * statusjson timestamps are epoch milliseconds; tolerate seconds too.
 * Zero / absent means "never".
 * @param {number | undefined} value
 * @returns {Date | null}
 */
function toDate(value) {
  if (!value) return null;
  return new Date(value > 1e11 ? value : value * 1000);
}

/**
 * Seconds -> "45s", "3m05s", "2h04m", "15d10h".
 * @param {number} seconds
 * @returns {string}
 */
function formatDuration(seconds) {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m${String(s % 60).padStart(2, '0')}s`;
  if (s < 86400) {
    return `${Math.floor(s / 3600)}h${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}m`;
  }
  return `${Math.floor(s / 86400)}d${String(Math.floor((s % 86400) / 3600)).padStart(2, '0')}h`;
}

/**
 * How long a row has been in its current state, or null if unknown.
 * @param {Service | Host} row
 * @param {Date} now
 * @returns {string | null}
 */
function stateDuration(row, now) {
  const since = toDate(row.last_state_change);
  return since ? formatDuration((now.getTime() - since.getTime()) / 1000) : null;
}

/**
 * "ack", "downtime" and "soft 1/3" markers of a row.
 * @param {Service | Host} row
 * @returns {string[]}
 */
function flags(row) {
  const out = [];
  if (row.problem_has_been_acknowledged) out.push('ack');
  if ((row.scheduled_downtime_depth ?? 0) > 0) out.push('downtime');
  if (row.state_type === 0 && row.max_attempts) {
    out.push(`soft ${row.current_attempt ?? 0}/${row.max_attempts}`);
  }
  if (row.checks_enabled === false) out.push('checks off');
  return out;
}

/**
 * Tree item description: state, time in state, markers.
 * @param {string} state
 * @param {Service | Host} row
 * @param {Date} now
 * @returns {string}
 */
function rowDescription(state, row, now) {
  const duration = stateDuration(row, now);
  return [state, ...(duration ? [duration] : []), ...flags(row)].join(' · ');
}

/**
 * @param {Service} svc
 * @param {Date} now
 * @returns {string}
 */
function serviceDescription(svc, now) {
  return rowDescription(serviceState(svc.status), svc, now);
}

/**
 * @param {Host} host
 * @param {Date} now
 * @returns {string}
 */
function hostDescription(host, now) {
  return rowDescription(hostState(host.status), host, now);
}

/**
 * Codicon id + theme colour id for a state; handled problems get a muted
 * "already on it" icon in the same colour.
 * @param {string} state
 * @param {Service | Host} row
 * @returns {[string, string | undefined]}
 */
function stateIcon(state, row) {
  const [icon, color] = STATE_ICONS[/** @type {keyof typeof STATE_ICONS} */ (state)] ?? [
    'circle-outline',
    undefined,
  ];
  if (row.problem_has_been_acknowledged) return ['bell-slash', color];
  if ((row.scheduled_downtime_depth ?? 0) > 0) return ['debug-pause', color];
  return [icon, color];
}

/**
 * @param {Date | null} date
 * @returns {string | undefined}
 */
function iso(date) {
  return date?.toISOString();
}

/**
 * Plain-text detail: a metadata header, then plugin output, long output
 * and performance data.
 * @param {string} title
 * @param {string} state
 * @param {Service | Host} row
 * @param {string} url web UI URL
 * @param {Date} now
 * @returns {string}
 */
function detailText(title, state, row, url, now) {
  const attempts = row.max_attempts
    ? `${row.current_attempt ?? 0}/${row.max_attempts} (${row.state_type === 1 ? 'hard' : 'soft'})`
    : undefined;
  /** @type {[string, string | null | undefined][]} */
  const rows = [
    ['State', state],
    ['Address', 'address' in row ? row.address : undefined],
    ['Duration', stateDuration(row, now)],
    ['Attempt', attempts],
    ['Flags', flags(row).join(', ')],
    ['Last check', iso(toDate(row.last_check))],
    ['Next check', iso(toDate(row.next_check))],
    ['Changed', iso(toDate(row.last_state_change))],
    ['URL', url],
  ];
  const header = rows
    .filter(([, value]) => value)
    .map(([key, value]) => `${key}:`.padEnd(12) + value);
  const sections = [
    (row.plugin_output || '(no output yet)').replace(/\s+$/, ''),
    ...(row.long_plugin_output ? [row.long_plugin_output.replace(/\s+$/, '')] : []),
    ...(row.perf_data ? [`Performance data:\n${row.perf_data.trim()}`] : []),
  ];
  return [title, ...header, '-'.repeat(72), sections.join('\n\n'), ''].join('\n');
}

/**
 * @param {Service} svc
 * @param {string} url
 * @param {Date} now
 * @returns {string}
 */
function serviceDetailText(svc, url, now) {
  return detailText(
    `Service ${svc.host_name} / ${svc.description}`,
    serviceState(svc.status),
    svc,
    url,
    now,
  );
}

/**
 * @param {Host} host
 * @param {string} url
 * @param {Date} now
 * @returns {string}
 */
function hostDetailText(host, url, now) {
  return detailText(`Host ${host.name}`, hostState(host.status), host, url, now);
}

module.exports = {
  formatDuration,
  hostDescription,
  hostDetailText,
  hostState,
  isHandled,
  isHostProblem,
  isServiceProblem,
  serviceDescription,
  serviceDetailText,
  serviceState,
  sortHostProblems,
  sortServiceProblems,
  stateDuration,
  stateIcon,
  toDate,
};
