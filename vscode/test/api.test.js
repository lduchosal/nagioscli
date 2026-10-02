const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { ApiError, NagiosApi, nodeTransport, strftime } = require('../src/api');

const cfg = {
  configFile: 'nagioscli.ini',
  url: 'https://mon.example/nagios',
  username: 'nagiosadmin',
  password: 'pw',
  passPath: null,
  vouchCookie: null,
  nginxToken: null,
  timeout: 7,
  verifySsl: false,
  startTimeFormat: '%m-%d-%Y %H:%M:%S',
};
const BASIC = { headers: { Authorization: 'Basic x' }, cookies: {} };
const NOW = new Date(2026, 9, 2, 8, 5, 9);

/** Transport answering each call with the next queued response. */
function fakeTransport(...responses) {
  const calls = [];
  const impl = async (url, req) => {
    calls.push({ url, req });
    const next = responses.length > 1 ? responses.shift() : responses[0];
    const { status = 200, body = '', setCookies = [] } = next;
    return { status, body: typeof body === 'string' ? body : JSON.stringify(body), setCookies };
  };
  return { impl, calls };
}

function makeApi(transport, auth = async () => BASIC) {
  return new NagiosApi(cfg, { transport, auth, now: () => NOW });
}

const ok = (data) => ({ body: { result: { type_code: 0 }, data } });

test('statusJson: GET statusjson.cgi with the credentials, timeout and SSL flag', async () => {
  const { impl, calls } = fakeTransport(ok({ host: { name: 'web01', status: 2 } }));
  assert.deepEqual(await makeApi(impl).getHost('web01'), { name: 'web01', status: 2 });
  assert.equal(
    calls[0].url,
    'https://mon.example/nagios/cgi-bin/statusjson.cgi?query=host&hostname=web01',
  );
  assert.deepEqual(calls[0].req, {
    method: 'GET',
    headers: { Authorization: 'Basic x' },
    body: undefined,
    timeoutMs: 7000,
    verifySsl: false,
  });
});

test('statusJson: a non-zero type_code or non-JSON body is an ApiError', async () => {
  const bad = fakeTransport({ body: { result: { type_code: 1, message: 'Bad query' } } });
  await assert.rejects(makeApi(bad.impl).listHosts(), /statusjson.cgi: Bad query/);
  const silent = fakeTransport({ body: {} });
  await assert.rejects(makeApi(silent.impl).listHosts(), /statusjson.cgi: Unknown error/);
  const html = fakeTransport({ body: '<html>' });
  await assert.rejects(makeApi(html.impl).listHosts(), /invalid JSON response/);
  const empty = fakeTransport({ body: { result: { type_code: 0 } } });
  assert.deepEqual(await makeApi(empty.impl).listHosts(), []);
});

test('service lists: flattened with details, bare integers tolerated', async () => {
  const { impl, calls } = fakeTransport(
    ok({
      servicelist: {
        web01: { HTTP: { status: 16, plugin_output: 'down' }, DISK: 4 },
        db01: null,
      },
    }),
  );
  const services = await makeApi(impl).listServiceProblems();
  assert.deepEqual(services, [
    { status: 16, plugin_output: 'down', host_name: 'web01', description: 'HTTP' },
    { status: 4, host_name: 'web01', description: 'DISK' },
  ]);
  assert.match(
    calls[0].url,
    /query=servicelist&details=true&servicestatus=warning\+critical\+unknown$/,
  );
  const empty = fakeTransport(ok({}));
  assert.deepEqual(await makeApi(empty.impl).listHostServices('web01'), []);
  assert.match(empty.calls[0].url, /query=servicelist&details=true&hostname=web01$/);
});

test('host lists: problems filter and the full list', async () => {
  const { impl, calls } = fakeTransport(ok({ hostlist: { web01: { status: 4 }, db01: 2 } }));
  const api = makeApi(impl);
  assert.deepEqual(await api.listHostProblems(), [
    { status: 4, name: 'web01' },
    { status: 2, name: 'db01' },
  ]);
  assert.match(calls[0].url, /query=hostlist&details=true&hoststatus=down\+unreachable$/);
  await api.listHosts();
  assert.match(calls[1].url, /query=hostlist&details=true$/);
});

test('getHost / getService: missing rows are a 404 ApiError', async () => {
  const { impl, calls } = fakeTransport(ok({}));
  const api = makeApi(impl);
  await assert.rejects(api.getHost('nope'), { status: 404, message: 'Host not found: nope' });
  await assert.rejects(api.getService('web01', 'Disk /'), {
    status: 404,
    message: 'Service not found: web01/Disk /',
  });
  assert.match(calls[1].url, /query=service&hostname=web01&servicedescription=Disk\+%2F$/);
  const found = fakeTransport(ok({ service: { status: 2 } }));
  assert.deepEqual(await makeApi(found.impl).getService('a', 'b'), { status: 2 });
});

test('HTTP errors carry the status; a 401 drops the cached credentials', async () => {
  let resolved = 0;
  const auth = async () => {
    resolved += 1;
    return BASIC;
  };
  const { impl } = fakeTransport({ status: 401 }, ok({ hostlist: {} }));
  const api = makeApi(impl, auth);
  await assert.rejects(api.listHosts(), (err) => {
    assert.ok(err instanceof ApiError);
    assert.equal(err.status, 401);
    assert.equal(err.message, 'statusjson.cgi: HTTP 401');
    return true;
  });
  await api.listHosts();
  await api.listHosts();
  assert.equal(resolved, 2, 're-resolved once after the 401, then cached');
  const server = fakeTransport({ status: 500 });
  await assert.rejects(makeApi(server.impl).listHosts(), { status: 500 });
});

test('transport failures become ApiError with status 0', async () => {
  const failing = async () => {
    throw new Error('ECONNREFUSED');
  };
  const rejecting = async () => {
    throw 'boom';
  };
  await assert.rejects(makeApi(failing).listHosts(), {
    status: 0,
    message: 'statusjson.cgi: connection error: ECONNREFUSED',
  });
  await assert.rejects(makeApi(rejecting).listHosts(), /connection error: boom$/);
});

test('auth: Vouch / nginx credentials become headers and cookies', async () => {
  const { impl, calls } = fakeTransport(ok({ hostlist: {} }));
  const api = makeApi(impl, async () => ({ headers: {}, cookies: { VouchCookie: 'vc' } }));
  await api.listHosts();
  assert.deepEqual(calls[0].req.headers, { Cookie: 'VouchCookie=vc' });
});

const PREFLIGHT = {
  body: "<form><input type='hidden' name='nagFormId' value='tok123'></form>",
  setCookies: ['other=1; Path=/', 'NagFormId=cookie456; Path=/nagios'],
};
const DONE = { body: '<p>Your command request was successfully submitted to Nagios</p>' };

test('forceCheck: CSRF preflight, then POST with the token, cookie and start_time', async () => {
  const { impl, calls } = fakeTransport(PREFLIGHT, DONE);
  await makeApi(impl).forceCheck('web01', 'HTTP');
  assert.equal(
    calls[0].url,
    'https://mon.example/nagios/cgi-bin/cmd.cgi?cmd_typ=7&host=web01&service=HTTP',
  );
  assert.equal(calls[0].req.method, 'GET');
  const post = calls[1];
  assert.equal(post.url, 'https://mon.example/nagios/cgi-bin/cmd.cgi');
  assert.equal(post.req.method, 'POST');
  assert.deepEqual(post.req.headers, {
    Authorization: 'Basic x',
    Cookie: 'NagFormId=cookie456',
    'Content-Type': 'application/x-www-form-urlencoded',
  });
  assert.deepEqual(Object.fromEntries(new URLSearchParams(post.req.body)), {
    cmd_typ: '7',
    host: 'web01',
    service: 'HTTP',
    cmd_mod: '2',
    start_time: '10-02-2026 08:05:09',
    force_check: 'on',
    btnSubmit: 'Commit',
    nagFormId: 'tok123',
  });
});

test('forceCheck on a host runs its own check (cmd_typ 96)', async () => {
  const { impl, calls } = fakeTransport({ body: '' }, DONE);
  await makeApi(impl).forceCheck('web01');
  assert.match(calls[0].url, /cmd.cgi\?cmd_typ=96&host=web01$/);
  const form = new URLSearchParams(calls[1].req.body);
  assert.equal(form.get('nagFormId'), '', 'still posts when Nagios < 4.4 sends no token');
  assert.equal(form.has('service'), false);
  assert.equal(calls[1].req.headers.Cookie, undefined);
});

test('acknowledge: sticky, notifying, with the comment (33 host / 34 service)', async () => {
  const { impl, calls } = fakeTransport(PREFLIGHT, DONE);
  const api = makeApi(impl);
  await api.acknowledge('web01', 'HTTP', 'on it');
  const form = Object.fromEntries(new URLSearchParams(calls[1].req.body));
  assert.equal(form.cmd_typ, '34');
  assert.equal(form.com_data, 'on it');
  assert.equal(form.sticky_ack, 'on');
  assert.equal(form.send_notification, 'on');
  await api.acknowledge('web01', undefined, 'host down');
  assert.match(calls[2].url, /cmd_typ=33&host=web01$/);
});

test('command: an unconfirmed POST surfaces the Nagios error message', async () => {
  const refused = fakeTransport(PREFLIGHT, {
    body: "<div class='errorMessage'> Sorry, but you are not authorized </div>",
  });
  await assert.rejects(
    makeApi(refused.impl).forceCheck('a'),
    /cmd.cgi: Sorry, but you are not authorized$/,
  );
  const blank = fakeTransport(PREFLIGHT, { body: '<html></html>' });
  await assert.rejects(
    makeApi(blank.impl).acknowledge('a', 'b', 'c'),
    /Nagios did not confirm the command/,
  );
});

test('strftime: the directives Nagios date formats use, others kept literally', () => {
  assert.equal(strftime('%Y-%m-%d %H:%M:%S', NOW), '2026-10-02 08:05:09');
  assert.equal(strftime('%d/%m/%y %% %Z', NOW), '02/10/26 % %Z');
});

test('webUrl: Nagios home, host and service extinfo pages', () => {
  const api = new NagiosApi(cfg);
  assert.equal(api.webUrl(), 'https://mon.example/nagios/');
  assert.equal(
    api.webUrl('web01'),
    'https://mon.example/nagios/cgi-bin/extinfo.cgi?type=1&host=web01',
  );
  assert.equal(
    api.webUrl('web01', 'Disk /'),
    'https://mon.example/nagios/cgi-bin/extinfo.cgi?type=2&host=web01&service=Disk+%2F',
  );
  assert.equal(typeof api.now().getTime(), 'number');
});

test('default auth provider resolves from the config', async () => {
  const { impl, calls } = fakeTransport(ok({ hostlist: {} }));
  await new NagiosApi({ ...cfg, nginxToken: 'nt' }, { transport: impl }).listHosts();
  assert.deepEqual(calls[0].req.headers, { 'X-API-Key': 'nt' });
});

/** Local HTTP server answering with `handler`; returns its base URL. */
async function serve(t, handler) {
  const server = http.createServer(handler);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  t.after(() => server.close());
  return `http://127.0.0.1:${server.address().port}`;
}

test('nodeTransport: real round trip (method, headers, body, cookies, cp1252 body)', async (t) => {
  const base = await serve(t, (req, res) => {
    let body = '';
    req.on('data', (chunk) => {
      body += chunk;
    });
    req.on('end', () => {
      res.writeHead(201, { 'Set-Cookie': ['NagFormId=abc; Path=/'] });
      const echo = JSON.stringify({ method: req.method, auth: req.headers.authorization, body });
      res.end(Buffer.concat([Buffer.from(`${echo} `), Buffer.from([0xe9])]));
    });
  });
  const resp = await nodeTransport(`${base}/cgi-bin/x`, {
    method: 'POST',
    headers: { Authorization: 'Basic t' },
    body: 'a=1',
    timeoutMs: 2000,
    verifySsl: false,
  });
  assert.equal(resp.status, 201);
  assert.deepEqual(resp.setCookies, ['NagFormId=abc; Path=/']);
  const cut = resp.body.lastIndexOf(' ');
  const [json, tail] = [resp.body.slice(0, cut), resp.body.slice(cut + 1)];
  assert.deepEqual(JSON.parse(json), { method: 'POST', auth: 'Basic t', body: 'a=1' });
  assert.equal(tail, 'é');
});

test('nodeTransport: no Set-Cookie header means an empty list', async (t) => {
  const base = await serve(t, (_req, res) => res.end('ok'));
  const req = { method: 'GET', headers: {}, timeoutMs: 2000, verifySsl: true };
  assert.deepEqual(await nodeTransport(`${base}/`, req), {
    status: 200,
    body: 'ok',
    setCookies: [],
  });
});

test('nodeTransport: timeout and connection errors reject', async (t) => {
  const base = await serve(t, () => {
    // never answers
  });
  const req = { method: 'GET', headers: {}, timeoutMs: 50, verifySsl: true };
  await assert.rejects(nodeTransport(`${base}/slow`, req), /timeout after 0.05s/);
  await assert.rejects(nodeTransport('http://127.0.0.1:1/', req), /ECONNREFUSED/);
});

test('nodeTransport: https with verify_ssl=false is accepted by node (no network)', async () => {
  // Port 1 refuses immediately: the call goes through the https branch and
  // its rejectUnauthorized option without needing a TLS server.
  const req = { method: 'GET', headers: {}, timeoutMs: 1000, verifySsl: false };
  await assert.rejects(nodeTransport('https://127.0.0.1:1/', req), /ECONNREFUSED/);
  await assert.rejects(nodeTransport('https://127.0.0.1:1/', { ...req, verifySsl: true }));
});
