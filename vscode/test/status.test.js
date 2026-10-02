const test = require('node:test');
const assert = require('node:assert/strict');
const s = require('../src/status');

const NOW = new Date('2026-10-02T12:00:00Z');
const MS = (iso) => new Date(iso).getTime();

test('state names, unknown codes spelled out', () => {
  assert.deepEqual([1, 2, 4, 8, 16, 3].map(s.serviceState), [
    'PENDING',
    'OK',
    'WARNING',
    'UNKNOWN',
    'CRITICAL',
    'UNKNOWN(3)',
  ]);
  assert.deepEqual([1, 2, 4, 8, 16].map(s.hostState), [
    'PENDING',
    'UP',
    'DOWN',
    'UNREACHABLE',
    'UNKNOWN(16)',
  ]);
});

test('problems: PENDING and OK / UP are not problems (like the CLI)', () => {
  assert.deepEqual(
    [1, 2, 4, 8, 16].map((status) => s.isServiceProblem({ status })),
    [false, false, true, true, true],
  );
  assert.deepEqual(
    [1, 2, 4, 8].map((status) => s.isHostProblem({ status })),
    [false, false, true, true],
  );
});

test('isHandled: acknowledged or in downtime', () => {
  assert.equal(s.isHandled({ status: 16 }), false);
  assert.equal(s.isHandled({ status: 16, problem_has_been_acknowledged: true }), true);
  assert.equal(s.isHandled({ status: 16, scheduled_downtime_depth: 1 }), true);
});

test('sortServiceProblems: unhandled, then severity, then host / service', () => {
  const rows = [
    { host_name: 'b', description: 'x', status: 4 },
    { host_name: 'a', description: 'z', status: 16, problem_has_been_acknowledged: true },
    { host_name: 'b', description: 'a', status: 16 },
    { host_name: 'a', description: 'y', status: 16 },
    { host_name: 'a', description: 'u', status: 8 },
    { host_name: 'a', description: 'p', status: 1 },
  ];
  assert.deepEqual(
    s.sortServiceProblems(rows).map((r) => `${r.host_name}/${r.description}`),
    ['a/y', 'b/a', 'a/u', 'b/x', 'a/p', 'a/z'],
  );
});

test('sortHostProblems: unhandled, DOWN before UNREACHABLE, then name', () => {
  const rows = [
    { name: 'c', status: 8 },
    { name: 'b', status: 4, scheduled_downtime_depth: 2 },
    { name: 'z', status: 4 },
    { name: 'a', status: 4 },
    { name: 'p', status: 1 },
  ];
  assert.deepEqual(
    s.sortHostProblems(rows).map((r) => r.name),
    ['a', 'z', 'c', 'p', 'b'],
  );
});

test('toDate: statusjson milliseconds, seconds tolerated, 0 is never', () => {
  assert.equal(s.toDate(0), null);
  assert.equal(s.toDate(undefined), null);
  assert.equal(s.toDate(MS('2026-10-02T11:00:00Z')).toISOString(), '2026-10-02T11:00:00.000Z');
  assert.equal(s.toDate(1790000000).getTime(), 1790000000000);
});

test('formatDuration', () => {
  assert.deepEqual([-5, 45, 185, 7440, 1332000].map(s.formatDuration), [
    '0s',
    '45s',
    '3m05s',
    '2h04m',
    '15d10h',
  ]);
});

test('descriptions: state, time in state and markers', () => {
  const svc = {
    host_name: 'web01',
    description: 'HTTP',
    status: 16,
    last_state_change: MS('2026-10-02T10:00:00Z'),
    problem_has_been_acknowledged: true,
    scheduled_downtime_depth: 1,
    state_type: 0,
    current_attempt: 1,
    max_attempts: 3,
    checks_enabled: false,
  };
  assert.equal(
    s.serviceDescription(svc, NOW),
    'CRITICAL · 2h00m · ack · downtime · soft 1/3 · checks off',
  );
  assert.equal(s.serviceDescription({ status: 2, state_type: 0 }, NOW), 'OK');
  assert.equal(
    s.serviceDescription({ status: 4, state_type: 0, max_attempts: 3 }, NOW),
    'WARNING · soft 0/3',
  );
  assert.equal(
    s.hostDescription({ name: 'h', status: 4, state_type: 1, max_attempts: 3 }, NOW),
    'DOWN',
  );
  assert.equal(s.stateDuration({ status: 2 }, NOW), null);
});

test('stateIcon: per state, muted when handled, fallback for odd states', () => {
  assert.deepEqual(s.stateIcon('CRITICAL', {}), ['error', 'testing.iconFailed']);
  assert.deepEqual(s.stateIcon('UP', {}), ['pass', 'testing.iconPassed']);
  assert.deepEqual(s.stateIcon('WARNING', { problem_has_been_acknowledged: true }), [
    'bell-slash',
    'list.warningForeground',
  ]);
  assert.deepEqual(s.stateIcon('DOWN', { scheduled_downtime_depth: 1 }), [
    'debug-pause',
    'testing.iconFailed',
  ]);
  assert.deepEqual(s.stateIcon('UNKNOWN(3)', {}), ['circle-outline', undefined]);
});

test('serviceDetailText: header, output, long output and perf data', () => {
  const text = s.serviceDetailText(
    {
      host_name: 'web01',
      description: 'HTTP',
      status: 16,
      plugin_output: 'CRITICAL - down  ',
      long_plugin_output: 'line 2\nline 3\n',
      perf_data: ' time=0.1s ',
      state_type: 1,
      current_attempt: 3,
      max_attempts: 3,
      last_check: MS('2026-10-02T11:59:00Z'),
      next_check: MS('2026-10-02T12:04:00Z'),
      last_state_change: MS('2026-10-02T11:00:00Z'),
    },
    'https://n/extinfo',
    NOW,
  );
  assert.equal(
    text,
    [
      'Service web01 / HTTP',
      'State:      CRITICAL',
      'Duration:   1h00m',
      'Attempt:    3/3 (hard)',
      'Last check: 2026-10-02T11:59:00.000Z',
      'Next check: 2026-10-02T12:04:00.000Z',
      'Changed:    2026-10-02T11:00:00.000Z',
      'URL:        https://n/extinfo',
      '-'.repeat(72),
      'CRITICAL - down',
      '',
      'line 2\nline 3',
      '',
      'Performance data:\ntime=0.1s',
      '',
    ].join('\n'),
  );
});

test('hostDetailText: address, soft attempts, no output yet', () => {
  const text = s.hostDetailText(
    { name: 'db01', status: 1, address: '10.0.0.2', state_type: 0, max_attempts: 5 },
    'https://n/h',
    NOW,
  );
  assert.match(text, /^Host db01\nState: {6}PENDING\nAddress: {4}10\.0\.0\.2\n/);
  assert.match(text, /Attempt: {4}0\/5 \(soft\)/);
  assert.match(text, /Flags: {6}soft 0\/5/);
  assert.match(text, /\(no output yet\)\n$/);
});
