// @ts-check
// Thin client over the Nagios Core CGIs, port of nagioscli/core/client.py:
// statusjson.cgi for the state, cmd.cgi (with the Nagios 4.4+ CSRF
// preflight) for forced checks and acknowledgements.
//
// Transport is node:http(s), not the global fetch: inside VS Code the https
// module is patched to honour the OS trust store and the proxy settings,
// and it is the only way to apply verify_ssl = false without bundling
// undici. No runtime dependencies.

const http = require('node:http');
const https = require('node:https');
const { authHeaders } = require('./config');
const { decodeBody } = require('./encoding');

const STATUS_JSON = 'statusjson.cgi';
const SUCCESS_MARKER = 'successfully submitted';
// cmd.cgi command types (include/common.h).
const CMD_SCHEDULE_FORCED_SVC_CHECK = '7';
const CMD_SCHEDULE_FORCED_HOST_CHECK = '96';
const CMD_ACKNOWLEDGE_HOST_PROBLEM = '33';
const CMD_ACKNOWLEDGE_SVC_PROBLEM = '34';
const CMD_MOD_COMMIT = '2';
// Nagios 4.4+ CSRF: GET cmd.cgi sets a NagFormId cookie and a matching
// hidden nagFormId field; the POST must echo both.
const NAGFORM_INPUT = /<input[^>]*\bname=['"]nagFormId['"][^>]*\bvalue=['"]([^'"]+)['"]/i;
const NAGFORM_COOKIE = /\bNagFormId=([^;\s]+)/;
const ERROR_MESSAGE = /<div class=['"]errorMessage['"]>([^<]*)</i;

/**
 * A service row of statusjson.cgi (servicelist with details, or service).
 * Only the fields the extension reads are typed.
 * @typedef {object} Service
 * @property {string} host_name
 * @property {string} description
 * @property {number} status SERVICE_* bitmask (1 pending, 2 ok, 4 warning, 8 unknown, 16 critical)
 * @property {string} [plugin_output]
 * @property {string} [long_plugin_output]
 * @property {string} [perf_data]
 * @property {number} [current_attempt]
 * @property {number} [max_attempts]
 * @property {number} [state_type] 0 soft, 1 hard
 * @property {boolean} [problem_has_been_acknowledged]
 * @property {number} [scheduled_downtime_depth]
 * @property {boolean} [checks_enabled]
 * @property {boolean} [notifications_enabled]
 * @property {number} [last_check] epoch (ms in statusjson)
 * @property {number} [next_check]
 * @property {number} [last_state_change]
 */

/**
 * A host row of statusjson.cgi (hostlist with details, or host).
 * @typedef {object} Host
 * @property {string} name
 * @property {number} status HOST_* bitmask (1 pending, 2 up, 4 down, 8 unreachable)
 * @property {string} [address]
 * @property {string} [plugin_output]
 * @property {string} [long_plugin_output]
 * @property {string} [perf_data]
 * @property {number} [current_attempt]
 * @property {number} [max_attempts]
 * @property {number} [state_type]
 * @property {boolean} [problem_has_been_acknowledged]
 * @property {number} [scheduled_downtime_depth]
 * @property {boolean} [checks_enabled]
 * @property {boolean} [notifications_enabled]
 * @property {number} [last_check]
 * @property {number} [next_check]
 * @property {number} [last_state_change]
 */

/**
 * @typedef {object} RawResponse
 * @property {number} status
 * @property {string} body
 * @property {string[]} setCookies
 */

/**
 * @typedef {object} TransportRequest
 * @property {string} method
 * @property {Record<string, string>} headers
 * @property {string} [body]
 * @property {number} timeoutMs
 * @property {boolean} verifySsl
 */

/** @typedef {(url: string, req: TransportRequest) => Promise<RawResponse>} Transport */
/** @typedef {(cfg: import('./config').NagiosConfig) => ReturnType<typeof authHeaders>} AuthProvider */

/** Error carrying the HTTP status (0 for network / protocol errors). */
class ApiError extends Error {
  /**
   * @param {string} message
   * @param {number} status
   */
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

/** @type {Transport} */
function nodeTransport(url, req) {
  const target = new URL(url);
  const mod = target.protocol === 'http:' ? http : https;
  return new Promise((resolve, reject) => {
    const request = mod.request(
      target,
      {
        method: req.method,
        headers: req.headers,
        timeout: req.timeoutMs,
        // Opt-in insecure mode (verify_ssl = false, the nagioscli default):
        // self-signed Nagios certificates are the common case.
        ...(target.protocol === 'https:' && !req.verifySsl ? { rejectUnauthorized: false } : {}),
      },
      (res) => {
        /** @type {Buffer[]} */
        const chunks = [];
        res.on('data', (chunk) => chunks.push(chunk));
        res.on('end', () =>
          resolve({
            status: res.statusCode ?? 0,
            body: decodeBody(Buffer.concat(chunks)),
            setCookies: res.headers['set-cookie'] ?? [],
          }),
        );
        res.on('error', reject);
      },
    );
    request.on('timeout', () =>
      request.destroy(new Error(`timeout after ${req.timeoutMs / 1000}s`)),
    );
    request.on('error', reject);
    request.end(req.body);
  });
}

/**
 * Python strftime subset used by cmd.cgi start_time formats
 * (%Y %y %m %d %H %M %S %%); any other directive is kept literally.
 * @param {string} format
 * @param {Date} date local time
 * @returns {string}
 */
function strftime(format, date) {
  const pad = (/** @type {number} */ n) => String(n).padStart(2, '0');
  /** @type {Record<string, string>} */
  const fields = {
    Y: String(date.getFullYear()),
    y: pad(date.getFullYear() % 100),
    m: pad(date.getMonth() + 1),
    d: pad(date.getDate()),
    H: pad(date.getHours()),
    M: pad(date.getMinutes()),
    S: pad(date.getSeconds()),
    '%': '%',
  };
  return format.replaceAll(/%(.)/g, (match, code) => fields[code] ?? match);
}

/**
 * Rows of a details=true list ({host: {svc: row}} or {host: row}). Without
 * details Nagios answers bare status integers: those are wrapped too.
 * @param {unknown} value
 * @returns {Record<string, any>}
 */
function asRow(value) {
  return typeof value === 'object' && value !== null ? value : { status: value };
}

class NagiosApi {
  /**
   * @param {import('./config').NagiosConfig} cfg
   * @param {{ transport?: Transport, auth?: AuthProvider, now?: () => Date }} [opts]
   */
  constructor(cfg, opts = {}) {
    this.cfg = cfg;
    this.transport = opts.transport ?? nodeTransport;
    this.auth = opts.auth ?? ((/** @type {import('./config').NagiosConfig} */ c) => authHeaders(c));
    this.now = opts.now ?? (() => new Date());
    /** @type {Awaited<ReturnType<AuthProvider>> | null} resolved once (pass can prompt) */
    this.credentials = null;
  }

  /** @returns {Promise<Awaited<ReturnType<AuthProvider>>>} */
  async getCredentials() {
    this.credentials ??= await this.auth(this.cfg);
    return this.credentials;
  }

  /**
   * One CGI round trip with the configured credentials.
   * @param {string} method
   * @param {string} cgi e.g. 'statusjson.cgi'
   * @param {URLSearchParams} params query (GET) or form body (POST)
   * @param {Record<string, string>} [cookies] extra cookies (CSRF)
   * @returns {Promise<RawResponse>}
   */
  async request(method, cgi, params, cookies = {}) {
    const creds = await this.getCredentials();
    /** @type {Record<string, string>} */
    const headers = { ...creds.headers };
    const allCookies = { ...cookies, ...creds.cookies };
    const cookieHeader = Object.entries(allCookies)
      .map(([k, v]) => `${k}=${v}`)
      .join('; ');
    if (cookieHeader) headers.Cookie = cookieHeader;
    const isPost = method === 'POST';
    if (isPost) headers['Content-Type'] = 'application/x-www-form-urlencoded';
    const query = isPost ? '' : `?${params}`;
    const url = `${this.cfg.url}/cgi-bin/${cgi}${query}`;
    let resp;
    try {
      resp = await this.transport(url, {
        method,
        headers,
        body: isPost ? params.toString() : undefined,
        timeoutMs: this.cfg.timeout * 1000,
        verifySsl: this.cfg.verifySsl,
      });
    } catch (err) {
      throw new ApiError(
        `${cgi}: connection error: ${err instanceof Error ? err.message : err}`,
        0,
      );
    }
    if (resp.status < 200 || resp.status >= 300) {
      if (resp.status === 401) this.credentials = null;
      throw new ApiError(`${cgi}: HTTP ${resp.status}`, resp.status);
    }
    return resp;
  }

  /**
   * statusjson.cgi query, checked like the CLI (result.type_code == 0).
   * @param {Record<string, string>} query
   * @returns {Promise<Record<string, any>>} the `data` member
   */
  async statusJson(query) {
    const resp = await this.request('GET', STATUS_JSON, new URLSearchParams(query));
    let json;
    try {
      json = JSON.parse(resp.body);
    } catch {
      throw new ApiError(`${STATUS_JSON}: invalid JSON response`, 0);
    }
    if (json?.result?.type_code !== 0) {
      throw new ApiError(`${STATUS_JSON}: ${json?.result?.message ?? 'Unknown error'}`, 0);
    }
    return json.data ?? {};
  }

  /**
   * @param {Record<string, string>} query servicelist filters
   * @returns {Promise<Service[]>}
   */
  async serviceList(query) {
    const data = await this.statusJson({ query: 'servicelist', details: 'true', ...query });
    /** @type {Service[]} */
    const services = [];
    for (const [host, byService] of Object.entries(data.servicelist ?? {})) {
      for (const [description, value] of Object.entries(byService ?? {})) {
        services.push(/** @type {Service} */ ({ ...asRow(value), host_name: host, description }));
      }
    }
    return services;
  }

  /**
   * @param {Record<string, string>} query hostlist filters
   * @returns {Promise<Host[]>}
   */
  async hostList(query) {
    const data = await this.statusJson({ query: 'hostlist', details: 'true', ...query });
    return Object.entries(data.hostlist ?? {}).map(
      ([name, value]) => /** @type {Host} */ ({ ...asRow(value), name }),
    );
  }

  /** Services in WARNING / CRITICAL / UNKNOWN (the CLI's `problems`). */
  listServiceProblems() {
    return this.serviceList({ servicestatus: 'warning critical unknown' });
  }

  /** Hosts DOWN or UNREACHABLE. */
  listHostProblems() {
    return this.hostList({ hoststatus: 'down unreachable' });
  }

  /** Every monitored host. */
  listHosts() {
    return this.hostList({});
  }

  /**
   * @param {string} host
   * @returns {Promise<Service[]>}
   */
  listHostServices(host) {
    return this.serviceList({ hostname: host });
  }

  /**
   * @param {string} host
   * @returns {Promise<Host>}
   */
  async getHost(host) {
    const data = await this.statusJson({ query: 'host', hostname: host });
    if (!data.host) throw new ApiError(`Host not found: ${host}`, 404);
    return data.host;
  }

  /**
   * @param {string} host
   * @param {string} service
   * @returns {Promise<Service>}
   */
  async getService(host, service) {
    const data = await this.statusJson({
      query: 'service',
      hostname: host,
      servicedescription: service,
    });
    if (!data.service) throw new ApiError(`Service not found: ${host}/${service}`, 404);
    return data.service;
  }

  /**
   * POST cmd.cgi after the CSRF preflight; resolves once Nagios confirms.
   * @param {Record<string, string>} fields command fields (cmd_typ, host, service…)
   * @param {Record<string, string>} extra commit-only fields
   * @returns {Promise<void>}
   */
  async command(fields, extra) {
    const preflight = await this.request('GET', 'cmd.cgi', new URLSearchParams(fields));
    const cookie = preflight.setCookies.map((c) => NAGFORM_COOKIE.exec(c)?.[1]).find(Boolean);
    const token = NAGFORM_INPUT.exec(preflight.body)?.[1] ?? '';
    const form = new URLSearchParams({
      ...fields,
      cmd_mod: CMD_MOD_COMMIT,
      ...extra,
      btnSubmit: 'Commit',
      nagFormId: token,
    });
    const resp = await this.request('POST', 'cmd.cgi', form, cookie ? { NagFormId: cookie } : {});
    if (!resp.body.toLowerCase().includes(SUCCESS_MARKER)) {
      const reason = ERROR_MESSAGE.exec(resp.body)?.[1].trim();
      throw new ApiError(`cmd.cgi: ${reason || 'Nagios did not confirm the command'}`, 0);
    }
  }

  /**
   * @param {string} host
   * @param {string} [service]
   * @returns {Record<string, string>}
   */
  static target(host, service) {
    return service === undefined ? { host } : { host, service };
  }

  /**
   * Force an immediate check of a service, or of the host itself
   * (cmd_typ 96, its own check_command — not its services).
   * @param {string} host
   * @param {string} [service]
   * @returns {Promise<void>}
   */
  forceCheck(host, service) {
    const type =
      service === undefined ? CMD_SCHEDULE_FORCED_HOST_CHECK : CMD_SCHEDULE_FORCED_SVC_CHECK;
    return this.command(
      { cmd_typ: type, ...NagiosApi.target(host, service) },
      { start_time: strftime(this.cfg.startTimeFormat, this.now()), force_check: 'on' },
    );
  }

  /**
   * Sticky acknowledgement with notification, like `nagioscli ack`.
   * @param {string} host
   * @param {string | undefined} service
   * @param {string} comment
   * @returns {Promise<void>}
   */
  acknowledge(host, service, comment) {
    const type = service === undefined ? CMD_ACKNOWLEDGE_HOST_PROBLEM : CMD_ACKNOWLEDGE_SVC_PROBLEM;
    return this.command(
      { cmd_typ: type, ...NagiosApi.target(host, service) },
      { com_data: comment, sticky_ack: 'on', send_notification: 'on' },
    );
  }

  /**
   * Web UI URL: the Nagios home, or the extinfo page of a host / service.
   * @param {string} [host]
   * @param {string} [service]
   * @returns {string}
   */
  webUrl(host, service) {
    if (host === undefined) return `${this.cfg.url}/`;
    const query = new URLSearchParams({ type: service === undefined ? '1' : '2', host });
    if (service !== undefined) query.set('service', service);
    return `${this.cfg.url}/cgi-bin/extinfo.cgi?${query}`;
  }
}

module.exports = { ApiError, NagiosApi, nodeTransport, strftime };
