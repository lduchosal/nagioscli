const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {
  ConfigError,
  authHeaders,
  findConfigFile,
  loadCachedVouchToken,
  loadConfig,
  parseConfig,
  parseIni,
  readPass,
} = require('../src/config');

function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'nagioscli-vsc-'));
}

const BASE = '[nagios]\nurl = https://mon.example/nagios/\nusername = nagiosadmin\n';

/** A parsed config with every credential empty, for authHeaders tests. */
function bare(overrides = {}) {
  return { ...parseConfig(BASE, '/x/nagioscli.ini', {}), ...overrides };
}

test('parseIni: sections, both separators, comments, case-insensitive keys, BOM', () => {
  const ini = parseIni(
    '﻿# top\n[nagios]\nURL = https://x\n; c\nusername: admin\n  continuation\n[auth]\nmethod=env_var\nnoequals\n',
  );
  assert.deepEqual(ini, {
    nagios: { url: 'https://x', username: 'admin' },
    auth: { method: 'env_var' },
  });
});

test('parseIni: keys before any section are ignored, % stays literal', () => {
  assert.deepEqual(parseIni('orphan = 1\n[s]\nk = %d-%m-%Y\n'), { s: { k: '%d-%m-%Y' } });
});

test('parseConfig: defaults like the CLI (verify_ssl false, timeout 30, us dates)', () => {
  const cfg = parseConfig(BASE, '/x/nagioscli.ini', {});
  assert.deepEqual(cfg, {
    configFile: '/x/nagioscli.ini',
    url: 'https://mon.example/nagios',
    username: 'nagiosadmin',
    password: null,
    passPath: null,
    vouchCookie: null,
    nginxToken: null,
    timeout: 30,
    verifySsl: false,
    startTimeFormat: '%m-%d-%Y %H:%M:%S',
  });
});

test('parseConfig: password in [nagios] when there is no [auth] section', () => {
  assert.equal(parseConfig(`${BASE}password = legacy\n`, 'f', {}).password, 'legacy');
});

test('parseConfig: every [auth] method', () => {
  const auth = (body, env = {}) => parseConfig(`${BASE}[auth]\n${body}`, 'f', env);
  assert.equal(auth('password = pw\n').password, 'pw');
  assert.equal(auth('method = password\n').password, null);
  assert.equal(auth('method = pass_path\npass_path = nagios/admin\n').passPath, 'nagios/admin');
  assert.equal(auth('method = pass_path\n').passPath, null);
  assert.equal(auth('method = env_var\n', { NAGIOS_PASSWORD: 'e1' }).password, 'e1');
  assert.equal(auth('method = env_var\nenv_var = MY_PW\n', { MY_PW: 'e2' }).password, 'e2');
  assert.equal(auth('method = env_var\n').password, null);
  assert.equal(auth('method = vouch_cookie\nvouch_cookie = vc\n').vouchCookie, 'vc');
  assert.equal(auth('method = vouch_cookie\n').vouchCookie, null);
  assert.equal(auth('method = nginx_token\nnginx_token = nt\n').nginxToken, 'nt');
  assert.equal(auth('method = nginx_token\n').nginxToken, null);
  const unknown = auth('method = oauth\npassword = pw\n');
  assert.equal(unknown.password, null);
  assert.equal(unknown.nginxToken, null);
});

test('parseConfig: [settings] timeout, verify_ssl, start_time_format', () => {
  const cfg = parseConfig(
    `${BASE}[settings]\ntimeout = 5\nverify_ssl = On\nstart_time_format = %d-%m-%Y %H:%M:%S\n`,
    'f',
    {},
  );
  assert.equal(cfg.timeout, 5);
  assert.equal(cfg.verifySsl, true);
  assert.equal(cfg.startTimeFormat, '%d-%m-%Y %H:%M:%S');
  assert.equal(parseConfig(`${BASE}[settings]\nverify_ssl = no\n`, 'f', {}).verifySsl, false);
  assert.throws(
    () => parseConfig(`${BASE}[settings]\nverify_ssl = maybe\n`, 'f', {}),
    /verify_ssl: not a boolean: maybe/,
  );
  assert.throws(
    () => parseConfig(`${BASE}[settings]\ntimeout = soon\n`, 'f', {}),
    /timeout: not an integer: soon/,
  );
});

test('parseConfig: plain http is accepted (the CLI has no allow_http)', () => {
  const ini = '[nagios]\nurl = http://mon/nagios\nusername = a\n';
  assert.equal(parseConfig(ini, 'f', {}).url, 'http://mon/nagios');
});

test('parseConfig: missing section / url / username', () => {
  assert.throws(() => parseConfig('[auth]\n', 'f', {}), /Missing \[nagios\] section/);
  assert.throws(() => parseConfig('[nagios]\nusername = a\n', 'f', {}), /Missing 'url'/);
  assert.throws(() => parseConfig('[nagios]\nurl = https://x\n', 'f', {}), /Missing 'username'/);
});

test('findConfigFile: walks up from the workspace, then ~/.nagioscli.ini', () => {
  const root = tmpdir();
  const sub = path.join(root, 'a', 'b');
  fs.mkdirSync(sub, { recursive: true });
  const home = tmpdir();
  const homeIni = path.join(home, '.nagioscli.ini');
  fs.writeFileSync(homeIni, BASE);
  assert.equal(findConfigFile(sub, home), homeIni);
  fs.writeFileSync(path.join(root, 'nagioscli.ini'), BASE);
  assert.equal(findConfigFile(sub, home), path.join(root, 'nagioscli.ini'));
});

test('loadConfig: reads the file found, reports when there is none', () => {
  const emptyHome = tmpdir();
  const root = tmpdir();
  assert.throws(() => loadConfig(root, {}, emptyHome), /No nagioscli.ini found/);
  const file = path.join(root, 'nagioscli.ini');
  fs.writeFileSync(file, `${BASE}password = pw\n`);
  const cfg = loadConfig(root, {}, emptyHome);
  assert.equal(cfg.configFile, file);
  assert.equal(cfg.password, 'pw');
  assert.equal(typeof loadConfig(root).url, 'string');
});

test('loadCachedVouchToken: ~/.nagioscli_token, trimmed; empty or missing is null', () => {
  const home = tmpdir();
  assert.equal(loadCachedVouchToken(home), null);
  fs.writeFileSync(path.join(home, '.nagioscli_token'), ' tok \n');
  assert.equal(loadCachedVouchToken(home), 'tok');
  fs.writeFileSync(path.join(home, '.nagioscli_token'), '\n');
  assert.equal(loadCachedVouchToken(home), null);
  assert.ok(loadCachedVouchToken() === null || typeof loadCachedVouchToken() === 'string');
});

test('authHeaders: nginx_token wins over everything', async () => {
  const home = tmpdir();
  fs.writeFileSync(path.join(home, '.nagioscli_token'), 'cached');
  const creds = await authHeaders(bare({ nginxToken: 'nt', password: 'pw' }), { home });
  assert.deepEqual(creds, { headers: { 'X-API-Key': 'nt' }, cookies: {} });
});

test('authHeaders: cached Vouch token, then the config cookie', async () => {
  const home = tmpdir();
  const cfg = bare({ vouchCookie: 'from-ini', password: 'pw' });
  assert.deepEqual(await authHeaders(cfg, { home }), {
    headers: {},
    cookies: { VouchCookie: 'from-ini' },
  });
  fs.writeFileSync(path.join(home, '.nagioscli_token'), 'cached');
  assert.deepEqual((await authHeaders(bare(), { home })).cookies, { VouchCookie: 'cached' });
});

test('authHeaders: preemptive Basic auth from password or pass', async () => {
  const home = tmpdir();
  const basic = (pw) => `Basic ${Buffer.from(`nagiosadmin:${pw}`).toString('base64')}`;
  const direct = await authHeaders(bare({ password: 'pw' }), { home });
  assert.deepEqual(direct, { headers: { Authorization: basic('pw') }, cookies: {} });
  const asked = [];
  const viaPass = await authHeaders(bare({ passPath: 'nagios/admin' }), {
    home,
    readPass: async (p) => {
      asked.push(p);
      return 'secret';
    },
  });
  assert.deepEqual(asked, ['nagios/admin']);
  assert.equal(viaPass.headers.Authorization, basic('secret'));
});

test('authHeaders: no credential at all is a ConfigError', async () => {
  await assert.rejects(authHeaders(bare(), { home: tmpdir() }), (err) => {
    assert.ok(err instanceof ConfigError);
    assert.match(err.message, /No password configured in \/x\/nagioscli.ini/);
    return true;
  });
});

test('authHeaders: default options read the real home', async () => {
  // nginx_token short-circuits before any file or `pass` access.
  assert.deepEqual((await authHeaders(bare({ nginxToken: '' }))).headers, { 'X-API-Key': '' });
});

/** A fake `pass` executable on PATH answering with `script`. */
function fakePass(t, script) {
  const dir = tmpdir();
  const bin = path.join(dir, 'pass');
  fs.writeFileSync(bin, `#!/bin/sh\n${script}\n`, { mode: 0o755 });
  const savedPath = process.env.PATH;
  process.env.PATH = `${dir}${path.delimiter}${savedPath}`;
  t.after(() => {
    process.env.PATH = savedPath;
  });
}

test('readPass: first line of `pass <path>`, trimmed', async (t) => {
  fakePass(t, 'echo "  s3cret  "');
  assert.equal(await readPass('nagios/admin'), 's3cret');
});

test('readPass: error exit, empty output, missing binary', async (t) => {
  fakePass(t, 'if [ "$1" = empty ]; then exit 0; fi; echo "not in store" >&2; exit 1');
  await assert.rejects(readPass('nagios/x'), /pass returned error: not in store/);
  await assert.rejects(readPass('empty'), /Empty password from pass for: empty/);
  const saved = process.env.PATH;
  process.env.PATH = tmpdir();
  t.after(() => {
    process.env.PATH = saved;
  });
  await assert.rejects(readPass('x'), /'pass' command not found/);
});

test('readPass: a failure without stderr reports the process error', async (t) => {
  fakePass(t, 'exit 3');
  await assert.rejects(readPass('x'), /pass returned error: Command failed/);
});
