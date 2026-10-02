// @ts-check
// Resolve the Nagios connection exactly like the `nagioscli` CLI does
// (nagioscli/core/config.py + core/auth.py): nagioscli.ini, the [auth]
// methods (password, pass_path, env_var, vouch_cookie, nginx_token), the
// Vouch token cached by `nagioscli login` and the [settings]. Pure Node —
// no `vscode` import — so it is testable with `node --test`.
//
// One deliberate difference: VS Code has no cwd, so the "current directory"
// step walks up from the workspace folder (opening a sub-folder of the
// project still finds its nagioscli.ini).

const childProcess = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const CONFIG_NAME = 'nagioscli.ini';
const TOKEN_CACHE_NAME = '.nagioscli_token';
const DEFAULT_ENV_VAR = 'NAGIOS_PASSWORD';
const DEFAULT_TIMEOUT = 30;
const DEFAULT_START_TIME_FORMAT = '%m-%d-%Y %H:%M:%S';
const PASS_TIMEOUT_MS = 10000;
const TRUE_WORDS = new Set(['1', 'yes', 'true', 'on']);
const FALSE_WORDS = new Set(['0', 'no', 'false', 'off']);

/**
 * @typedef {object} NagiosConfig
 * @property {string} configFile absolute path of the nagioscli.ini in use
 * @property {string} url base URL, no trailing slash (CGIs live under /cgi-bin)
 * @property {string} username
 * @property {string | null} password
 * @property {string | null} passPath password-store entry, read with `pass`
 * @property {string | null} vouchCookie
 * @property {string | null} nginxToken
 * @property {number} timeout seconds
 * @property {boolean} verifySsl
 * @property {string} startTimeFormat strftime format of cmd.cgi start_time
 */

/** @typedef {(passPath: string) => Promise<string>} PassReader */

/** Configuration / credential error with a message meant for the user. */
class ConfigError extends Error {}

/**
 * Walk up from `start` looking for a file named `name`.
 * @param {string} start
 * @param {string} name
 * @returns {string | null}
 */
function findFileUpwards(start, name) {
  let cur = path.resolve(start);
  for (;;) {
    const candidate = path.join(cur, name);
    if (fs.existsSync(candidate)) return candidate;
    const parent = path.dirname(cur);
    if (parent === cur) return null;
    cur = parent;
  }
}

/**
 * nagioscli's search order, with the cwd step replaced by a walk up from
 * the workspace folder: ./nagioscli.ini (upwards), ~/.nagioscli.ini,
 * /usr/local/etc/nagioscli.ini.
 * @param {string} startDir
 * @param {string} [home]
 * @returns {string | null}
 */
function findConfigFile(startDir, home = os.homedir()) {
  const candidates = [path.join(home, `.${CONFIG_NAME}`), path.join('/usr/local/etc', CONFIG_NAME)];
  return findFileUpwards(startDir, CONFIG_NAME) ?? candidates.find((p) => fs.existsSync(p)) ?? null;
}

/**
 * configparser subset: `[section]`, `key = value` / `key: value`, full-line
 * `#`/`;` comments, case-insensitive keys, indented continuation lines
 * ignored. Interpolation-free, like nagioscli (strftime `%` stay literal).
 * @param {string} text
 * @returns {Record<string, Record<string, string>>}
 */
function parseIni(text) {
  /** @type {Record<string, Record<string, string>>} */
  const sections = {};
  /** @type {Record<string, string> | null} */
  let current = null;
  for (const raw of text.replace(/^﻿/, '').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#') || line.startsWith(';') || /^\s/.test(raw)) continue;
    const section = /^\[(.+)\]$/.exec(line);
    if (section) {
      const name = section[1].trim();
      sections[name] ??= {};
      current = sections[name];
      continue;
    }
    const kv = /^([^=:]+)[=:](.*)$/.exec(line);
    if (kv && current) current[kv[1].trim().toLowerCase()] = kv[2].trim();
  }
  return sections;
}

/**
 * configparser getboolean().
 * @param {string | undefined} raw
 * @param {boolean} fallback
 * @param {string} key for the error message
 * @returns {boolean}
 */
function parseBool(raw, fallback, key) {
  if (raw === undefined) return fallback;
  const word = raw.toLowerCase();
  if (TRUE_WORDS.has(word)) return true;
  if (FALSE_WORDS.has(word)) return false;
  throw new ConfigError(`[settings] ${key}: not a boolean: ${raw}`);
}

/**
 * configparser getint() with a fallback.
 * @param {string | undefined} raw
 * @param {number} fallback
 * @param {string} key for the error message
 * @returns {number}
 */
function parseInteger(raw, fallback, key) {
  if (!raw) return fallback;
  if (!/^\d+$/.test(raw)) throw new ConfigError(`[settings] ${key}: not an integer: ${raw}`);
  return Number(raw);
}

/**
 * The credential fields of nagioscli's _parse_config: one [auth] method,
 * or `[nagios] password` when there is no [auth] section. An unknown
 * method yields no credential (the CLI ignores it the same way).
 * @param {Record<string, Record<string, string>>} ini
 * @param {Record<string, string | undefined>} env
 * @returns {Pick<NagiosConfig, 'password' | 'passPath' | 'vouchCookie' | 'nginxToken'>}
 */
function resolveAuth(ini, env) {
  const creds = { password: null, passPath: null, vouchCookie: null, nginxToken: null };
  const auth = ini.auth;
  if (!auth) return { ...creds, password: ini.nagios.password || null };
  const method = auth.method || 'password';
  if (method === 'password') return { ...creds, password: auth.password || null };
  if (method === 'pass_path') return { ...creds, passPath: auth.pass_path || null };
  if (method === 'env_var') {
    return { ...creds, password: env[auth.env_var || DEFAULT_ENV_VAR] || null };
  }
  if (method === 'vouch_cookie') return { ...creds, vouchCookie: auth.vouch_cookie || null };
  // nginx_token: the CLI tests `is not None`, so an empty value still counts.
  if (method === 'nginx_token') return { ...creds, nginxToken: auth.nginx_token ?? null };
  return creds;
}

/**
 * Parse nagioscli.ini text into a connection config.
 * @param {string} text
 * @param {string} configFile
 * @param {Record<string, string | undefined>} env
 * @returns {NagiosConfig}
 */
function parseConfig(text, configFile, env) {
  const ini = parseIni(text);
  if (!ini.nagios) throw new ConfigError('Missing [nagios] section in configuration');
  const url = ini.nagios.url;
  if (!url) throw new ConfigError("Missing 'url' in [nagios] section");
  const username = ini.nagios.username;
  if (!username) throw new ConfigError("Missing 'username' in [nagios] section");
  const settings = ini.settings ?? {};
  return {
    configFile,
    url: url.replace(/\/+$/, ''),
    username,
    ...resolveAuth(ini, env),
    timeout: parseInteger(settings.timeout, DEFAULT_TIMEOUT, 'timeout'),
    // Default false on purpose, like the CLI: self-signed Nagios is the norm.
    verifySsl: parseBool(settings.verify_ssl, false, 'verify_ssl'),
    startTimeFormat: settings.start_time_format || DEFAULT_START_TIME_FORMAT,
  };
}

/**
 * Find and load the config for a workspace folder.
 * @param {string} startDir
 * @param {Record<string, string | undefined>} [env]
 * @param {string} [home]
 * @returns {NagiosConfig}
 */
function loadConfig(startDir, env = process.env, home = os.homedir()) {
  const configFile = findConfigFile(startDir, home);
  if (!configFile) {
    throw new ConfigError(
      'No nagioscli.ini found (workspace and parents, ~/.nagioscli.ini, /usr/local/etc).',
    );
  }
  return parseConfig(fs.readFileSync(configFile, 'utf8'), configFile, env);
}

/**
 * The Vouch token saved by `nagioscli login` (~/.nagioscli_token), if any.
 * @param {string} [home]
 * @returns {string | null}
 */
function loadCachedVouchToken(home = os.homedir()) {
  const file = path.join(home, TOKEN_CACHE_NAME);
  if (!fs.existsSync(file)) return null;
  return fs.readFileSync(file, 'utf8').trim() || null;
}

/** @type {PassReader} */
function readPass(passPath) {
  return new Promise((resolve, reject) => {
    childProcess.execFile(
      'pass',
      [passPath],
      { timeout: PASS_TIMEOUT_MS, encoding: 'utf8' },
      (err, stdout, stderr) => {
        if (err) {
          const code = /** @type {NodeJS.ErrnoException} */ (err).code;
          if (code === 'ENOENT') {
            reject(new ConfigError("'pass' command not found. Install password-store."));
          } else {
            reject(new ConfigError(`pass returned error: ${String(stderr).trim() || err.message}`));
          }
          return;
        }
        const password = stdout.trim();
        if (password) resolve(password);
        else reject(new ConfigError(`Empty password from pass for: ${passPath}`));
      },
    );
  });
}

/**
 * Request headers carrying the credentials, in nagioscli's precedence:
 * nginx_token (X-API-Key) > Vouch cookie (cached token first, then the
 * config) > preemptive Basic auth (password, or `pass <pass_path>`).
 * @param {NagiosConfig} cfg
 * @param {{ home?: string, readPass?: PassReader }} [opts]
 * @returns {Promise<{ headers: Record<string, string>, cookies: Record<string, string> }>}
 */
async function authHeaders(cfg, opts = {}) {
  if (cfg.nginxToken !== null) return { headers: { 'X-API-Key': cfg.nginxToken }, cookies: {} };
  const vouch = loadCachedVouchToken(opts.home) ?? cfg.vouchCookie;
  if (vouch) return { headers: {}, cookies: { VouchCookie: vouch } };
  let password = cfg.password;
  if (!password && cfg.passPath) password = await (opts.readPass ?? readPass)(cfg.passPath);
  if (!password) {
    throw new ConfigError(
      `No password configured in ${cfg.configFile}: set [auth] password / pass_path / env_var, or run \`nagioscli login\`.`,
    );
  }
  const basic = Buffer.from(`${cfg.username}:${password}`).toString('base64');
  return { headers: { Authorization: `Basic ${basic}` }, cookies: {} };
}

module.exports = {
  ConfigError,
  authHeaders,
  findConfigFile,
  findFileUpwards,
  loadCachedVouchToken,
  loadConfig,
  parseConfig,
  parseIni,
  readPass,
};
