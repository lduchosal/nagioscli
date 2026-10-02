const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vscode = require('./vscode-stub');
const { activate, deactivate, nodeTarget, targetOf } = require('../src/extension');

const { stub } = vscode;
const NOW = new Date('2026-10-02T12:00:00Z');
const cfg = {
  configFile: 'f',
  url: 'https://mon.example/nagios',
  username: 'u',
  password: 'p',
  passPath: null,
  vouchCookie: null,
  nginxToken: null,
  timeout: 30,
  verifySsl: false,
  startTimeFormat: '%m-%d-%Y %H:%M:%S',
};

const HOSTS = [
  { name: 'web01', status: 2, plugin_output: 'PING OK' },
  { name: 'mail01', status: 4, plugin_output: 'PING CRITICAL' },
  { name: 'backup01', status: 8, problem_has_been_acknowledged: true },
];
const SERVICES = [
  { host_name: 'web01', description: 'DISK', status: 4, plugin_output: 'DISK WARNING' },
  { host_name: 'db01', description: 'DISK', status: 16, scheduled_downtime_depth: 1 },
  { host_name: 'web01', description: 'HTTP', status: 16 },
  { host_name: 'web01', description: 'NEW', status: 1 },
];

/** Fake NagiosApi recording what the extension asks for. */
function fakeApi(c = cfg) {
  const api = {
    cfg: c,
    hosts: HOSTS,
    services: SERVICES,
    actions: [],
    fail: {},
    async listHostProblems() {
      if (api.fail.list) throw api.fail.list;
      return api.hosts.filter((h) => h.status !== 2);
    },
    async listServiceProblems() {
      return api.services.filter((x) => x.status !== 2);
    },
    async listHosts() {
      return api.hosts;
    },
    async listHostServices(host) {
      if (api.fail.services) throw api.fail.services;
      return api.services.filter((x) => x.host_name === host);
    },
    async getHost(host) {
      if (api.fail.detail) throw api.fail.detail;
      return api.hosts.find((h) => h.name === host);
    },
    async getService(host, service) {
      return api.services.find((x) => x.host_name === host && x.description === service);
    },
    async forceCheck(host, service) {
      if (api.fail.action) throw api.fail.action;
      api.actions.push(['check', host, service]);
    },
    async acknowledge(host, service, comment) {
      api.actions.push(['ack', host, service, comment]);
    },
    webUrl(host, service) {
      return `https://mon.example/nagios/${host ?? ''}${service ? `/${service}` : ''}`;
    },
  };
  return api;
}

/** Activate against a fresh stub; returns the controller and the fake API. */
async function setup(t, { loadConfig = () => cfg, folders = true } = {}) {
  stub.reset();
  stub.folders = folders ? [{ uri: vscode.Uri.file('/ws') }] : undefined;
  const api = fakeApi();
  const made = [];
  const context = { subscriptions: [] };
  const controller = activate(context, {
    loadConfig,
    makeApi: (c) => {
      made.push(c);
      api.cfg = c;
      return api;
    },
    now: () => NOW,
  });
  await controller.refresh();
  t.after(() => controller.timer && clearInterval(controller.timer));
  return { controller, api, context, made };
}

async function roots(controller) {
  return controller.tree.getChildren();
}

test('tree: three groups with counts, badge of unhandled problems, host description', async (t) => {
  const { controller } = await setup(t);
  const [hosts, services, all] = await roots(controller);
  assert.deepEqual(
    hosts.items.map((h) => h.name),
    ['mail01', 'backup01'],
  );
  assert.deepEqual(
    services.items.map((x) => `${x.host_name}/${x.description}`),
    ['web01/HTTP', 'web01/DISK', 'db01/DISK'],
  );
  assert.deepEqual(
    all.items.map((h) => h.name),
    ['backup01', 'mail01', 'web01'],
  );
  const groupItems = [hosts, services, all].map((g) => controller.tree.getTreeItem(g));
  assert.deepEqual(
    groupItems.map((i) => [i.label, i.description, i.collapsibleState]),
    [
      ['Host problems', '2', 2],
      ['Service problems', '3', 2],
      ['All hosts', '3', 1],
    ],
  );
  // mail01, web01/HTTP, web01/DISK — backup01 (ack) and db01/DISK (downtime) are handled.
  assert.deepEqual(controller.view.badge, { value: 3, tooltip: '3 unhandled problems' });
  assert.equal(controller.view.description, 'mon.example');
});

test('tree: one problem, singular badge; none, no badge', async (t) => {
  const { controller, api } = await setup(t);
  api.hosts = [HOSTS[0]];
  api.services = [SERVICES[2]];
  await controller.refresh();
  assert.deepEqual(controller.view.badge, { value: 1, tooltip: '1 unhandled problem' });
  api.services = [];
  await controller.refresh();
  assert.equal(controller.view.badge, undefined);
});

test('tree: host and service items carry icon, context value, tooltip, command', async (t) => {
  const { controller } = await setup(t);
  const [hosts, services] = await roots(controller);
  const [mail, backup] = await controller.tree.getChildren(hosts);
  const item = controller.tree.getTreeItem(mail);
  assert.equal(item.label, 'mail01');
  assert.equal(item.id, 'problem:host:mail01');
  assert.equal(item.description, 'DOWN');
  assert.equal(item.collapsibleState, 0);
  assert.equal(item.iconPath.id, 'error');
  assert.equal(item.iconPath.color.id, 'testing.iconFailed');
  assert.equal(item.contextValue, 'host.problem');
  assert.match(item.tooltip.value, /\*\*mail01\*\*\n\nDOWN\n\n`PING CRITICAL`/);
  assert.deepEqual(item.command, {
    command: 'nagioscli.showStatus',
    title: 'Show status',
    arguments: [mail],
  });
  const acked = controller.tree.getTreeItem(backup);
  assert.equal(acked.contextValue, 'host.handled');
  assert.equal(acked.iconPath.id, 'bell-slash');
  assert.doesNotMatch(acked.tooltip.value, /`/);

  const [http, , dbDisk] = await controller.tree.getChildren(services);
  const svcItem = controller.tree.getTreeItem(http);
  assert.equal(svcItem.label, 'web01 / HTTP');
  assert.equal(svcItem.id, 'problem:service:web01/HTTP');
  assert.equal(svcItem.contextValue, 'service.problem');
  assert.equal(controller.tree.getTreeItem(dbDisk).contextValue, 'service.handled');
});

test('tree: All hosts expand to their services, sorted, lazily fetched', async (t) => {
  const { controller, api } = await setup(t);
  const [, , all] = await roots(controller);
  const hostNodes = await controller.tree.getChildren(all);
  const web = hostNodes.find((n) => n.host.name === 'web01');
  const webItem = controller.tree.getTreeItem(web);
  assert.equal(webItem.collapsibleState, 1);
  assert.equal(webItem.id, 'all:host:web01');
  assert.equal(webItem.contextValue, 'host.ok');
  assert.equal(webItem.iconPath.id, 'pass');
  const children = await controller.tree.getChildren(web);
  assert.deepEqual(
    children.map((n) => n.service.description),
    ['DISK', 'HTTP', 'NEW'],
  );
  const pending = controller.tree.getTreeItem(children[2]);
  assert.equal(pending.label, 'NEW');
  assert.equal(pending.contextValue, 'service.ok');
  assert.equal(pending.iconPath.id, 'clock');
  assert.deepEqual(await controller.tree.getChildren(children[0]), []);

  api.fail.services = new Error('HTTP 500');
  assert.deepEqual(await controller.tree.getChildren(web), [{ kind: 'message', text: 'HTTP 500' }]);
  const [hostsGroup] = await roots(controller);
  const [problemHost] = await controller.tree.getChildren(hostsGroup);
  assert.deepEqual(await controller.tree.getChildren(problemHost), []);
  controller.tree.api = null;
  assert.deepEqual(await controller.tree.getChildren(web), []);
});

test('tree: hideHandled drops acknowledged / downtime problems', async (t) => {
  const { controller } = await setup(t);
  stub.settings['nagioscli.hideHandled'] = true;
  const [hosts, services, all] = await roots(controller);
  assert.deepEqual(
    hosts.items.map((h) => h.name),
    ['mail01'],
  );
  assert.equal(services.items.length, 2);
  assert.equal(all.items.length, 3, 'All hosts keeps everything');
});

test('tree: config and API problems are shown as a message node', async (t) => {
  const bad = await setup(t, {
    loadConfig: () => {
      throw new Error('No nagioscli.ini found');
    },
  });
  const [msg] = await roots(bad.controller);
  assert.deepEqual(msg, { kind: 'message', text: 'No nagioscli.ini found' });
  assert.equal(bad.controller.tree.getTreeItem(msg).iconPath.id, 'warning');
  assert.equal(bad.controller.view.description, undefined);
  assert.equal(bad.controller.tree.unhandledCount, 0);

  const noFolder = await setup(t, { folders: false });
  assert.match((await roots(noFolder.controller))[0].text, /Open a folder/);

  const { controller, api } = await setup(t);
  api.fail.list = 'unreachable';
  await controller.refresh();
  assert.deepEqual(await roots(controller), [{ kind: 'message', text: 'unreachable' }]);
  controller.tree.error = null;
  assert.deepEqual(await roots(controller), []);
});

test('reload: the API is rebuilt only when nagioscli.ini changes', async (t) => {
  let current = cfg;
  const { controller, made } = await setup(t, { loadConfig: () => current });
  await controller.refresh();
  assert.equal(made.length, 1);
  current = { ...cfg, timeout: 5 };
  await controller.refresh();
  assert.equal(made.length, 2);
});

test('showStatus: opens a read-only log document rendered from the API', async (t) => {
  const { controller } = await setup(t);
  const service = { kind: 'service', service: SERVICES[2], scope: 'problem' };
  await stub.commands.get('nagioscli.showStatus')(service);
  const [[doc, options]] = stub.callsOf('showTextDocument');
  assert.equal(doc.uri.scheme, 'nagioscli-status');
  assert.equal(doc.uri.path, '/web01 _ HTTP.log');
  assert.deepEqual(targetOf(doc.uri), { host: 'web01', service: 'HTTP' });
  assert.deepEqual(options, { preview: true });
  assert.equal(stub.callsOf('setTextDocumentLanguage')[0][1], 'log');

  const provider = stub.docProviders.get('nagioscli-status');
  const text = await provider.provideTextDocumentContent(doc.uri);
  assert.match(text, /^Service web01 \/ HTTP\nState: {6}CRITICAL\n/);
  assert.match(text, /URL: {8}https:\/\/mon.example\/nagios\/web01\/HTTP/);

  await stub.commands.get('nagioscli.showStatus')({ kind: 'host', host: HOSTS[1], scope: 'all' });
  const hostDoc = stub.callsOf('showTextDocument')[1][0];
  assert.deepEqual(targetOf(hostDoc.uri), { host: 'mail01', service: undefined });
  assert.match(await provider.provideTextDocumentContent(hostDoc.uri), /^Host mail01\n/);

  await stub.commands.get('nagioscli.showStatus')({ kind: 'message', text: 'x' });
  assert.equal(stub.callsOf('showTextDocument').length, 2);
  assert.equal(controller.docs.tree, controller.tree);
});

test('documents: errors and unknown URIs render a message, never throw', async (t) => {
  const { controller, api } = await setup(t);
  const provider = stub.docProviders.get('nagioscli-status');
  const bogus = vscode.Uri.from({ scheme: 'nagioscli-status', path: '/x.log', query: '' });
  assert.match(await provider.provideTextDocumentContent(bogus), /nothing to show/);
  api.fail.detail = new Error('Host not found: gone');
  const uri = vscode.Uri.from({ scheme: 'nagioscli-status', path: '/g.log', query: 'host=gone' });
  assert.equal(
    await provider.provideTextDocumentContent(uri),
    'nagioscli: cannot load gone: Host not found: gone\n',
  );
  const svc = vscode.Uri.from({
    scheme: 'nagioscli-status',
    path: '/g.log',
    query: 'host=web01&service=GONE',
  });
  assert.match(await provider.provideTextDocumentContent(svc), /cannot load web01 \/ GONE: /);
  controller.tree.api = null;
  assert.match(await provider.provideTextDocumentContent(uri), /nothing to show/);
});

test('refresh: re-renders every open status document, nothing else', async (t) => {
  const { controller } = await setup(t);
  const provider = stub.docProviders.get('nagioscli-status');
  const uri = (q) => vscode.Uri.from({ scheme: 'nagioscli-status', path: '/x.log', query: q });
  stub.documents.push({ uri: uri('host=a') }, { uri: vscode.Uri.file('/a') });
  provider.emitter.fired = [];
  await controller.refresh();
  assert.deepEqual(
    provider.emitter.fired.map((u) => u.query),
    ['host=a'],
  );
});

test('forceCheck: service and host, status bar on success, error message on failure', async (t) => {
  const { api } = await setup(t);
  await stub.commands.get('nagioscli.forceCheck')({
    kind: 'service',
    service: SERVICES[2],
    scope: 'problem',
  });
  await stub.commands.get('nagioscli.forceCheck')({ kind: 'host', host: HOSTS[1], scope: 'all' });
  assert.deepEqual(api.actions, [
    ['check', 'web01', 'HTTP'],
    ['check', 'mail01', undefined],
  ]);
  assert.deepEqual(
    stub.callsOf('setStatusBarMessage').map(([m]) => m),
    ['nagioscli: check of web01 / HTTP scheduled', 'nagioscli: check of mail01 scheduled'],
  );
  api.fail.action = new Error('cmd.cgi: Sorry');
  await stub.commands.get('nagioscli.forceCheck')({ kind: 'host', host: HOSTS[1], scope: 'all' });
  assert.deepEqual(stub.callsOf('showErrorMessage'), [['nagioscli: cmd.cgi: Sorry']]);
  await stub.commands.get('nagioscli.forceCheck')(undefined);
  assert.equal(api.actions.length, 2);
});

test('forceCheck: nothing happens without an API', async (t) => {
  const { controller, api } = await setup(t);
  controller.tree.api = null;
  await stub.commands.get('nagioscli.forceCheck')({ kind: 'host', host: HOSTS[1], scope: 'all' });
  assert.deepEqual(api.actions, []);
});

test('acknowledge: asks for a comment, trims it, cancelled or empty does nothing', async (t) => {
  const { controller, api } = await setup(t);
  const node = { kind: 'service', service: SERVICES[2], scope: 'problem' };
  stub.answers.push('  on it  ');
  await stub.commands.get('nagioscli.acknowledge')(node);
  assert.deepEqual(api.actions, [['ack', 'web01', 'HTTP', 'on it']]);
  const [[options]] = stub.callsOf('showInputBox');
  assert.equal(options.title, 'Acknowledge web01 / HTTP');
  assert.equal(options.validateInput(' '), 'A comment is required');
  assert.equal(options.validateInput('x'), null);
  assert.equal(stub.callsOf('setStatusBarMessage')[0][0], 'nagioscli: web01 / HTTP acknowledged');

  stub.answers.push(undefined);
  await stub.commands.get('nagioscli.acknowledge')(node);
  stub.answers.push('   ');
  await stub.commands.get('nagioscli.acknowledge')(node);
  await stub.commands.get('nagioscli.acknowledge')({ kind: 'message', text: 'x' });
  controller.tree.api = null;
  await stub.commands.get('nagioscli.acknowledge')(node);
  assert.equal(api.actions.length, 1);
  assert.equal(stub.callsOf('showInputBox').length, 3);
});

test('open in browser: Nagios home, one host or service', async (t) => {
  const { controller } = await setup(t);
  await stub.commands.get('nagioscli.openNagios')();
  await stub.commands.get('nagioscli.openInNagios')({ kind: 'host', host: HOSTS[0], scope: 'all' });
  await stub.commands.get('nagioscli.openInNagios')({
    kind: 'service',
    service: SERVICES[0],
    scope: 'all',
  });
  assert.deepEqual(stub.callsOf('openExternal'), [
    ['https:https://mon.example/nagios/'],
    ['https:https://mon.example/nagios/web01'],
    ['https:https://mon.example/nagios/web01/DISK'],
  ]);
  controller.tree.api = null;
  await stub.commands.get('nagioscli.openNagios')();
  assert.equal(stub.callsOf('openExternal').length, 3);
});

test('refresh command and auto-refresh timer follow the settings', async (t) => {
  const { controller, api, context } = await setup(t);
  assert.ok(controller.timer, 'armed with the 60s default');
  api.services = [];
  api.hosts = [HOSTS[0]];
  await stub.commands.get('nagioscli.refresh')();
  assert.equal(controller.view.badge, undefined);

  stub.settings['nagioscli.autoRefreshSeconds'] = 0;
  for (const listener of stub.configListeners) listener({ affectsConfiguration: () => true });
  assert.equal(controller.timer, null);
  for (const listener of stub.configListeners) listener({ affectsConfiguration: () => false });
  for (const sub of context.subscriptions) sub.dispose();
});

test('auto-refresh ticks only while the window is focused', async (t) => {
  t.mock.timers.enable({ apis: ['setInterval'] });
  const { controller, api } = await setup(t);
  let calls = 0;
  const original = api.listHosts;
  api.listHosts = async () => {
    calls += 1;
    return original();
  };
  stub.focused = false;
  t.mock.timers.tick(60000);
  assert.equal(calls, 0);
  stub.focused = true;
  t.mock.timers.tick(60000);
  assert.equal(calls, 1);
  clearInterval(controller.timer);
});

test('nodeTarget / targetOf / deactivate', () => {
  assert.equal(nodeTarget(undefined), null);
  assert.equal(nodeTarget({ kind: 'group', key: 'all', items: [] }), null);
  assert.deepEqual(nodeTarget({ kind: 'host', host: { name: 'h' } }), {
    host: 'h',
    service: undefined,
    label: 'h',
  });
  assert.equal(targetOf(vscode.Uri.from({ scheme: 's', path: '/x', query: 'service=a' })), null);
  assert.equal(deactivate(), undefined);
});

test('activate without deps: real config loader, real API, errors as messages', async (t) => {
  stub.reset();
  // An empty HOME: never reach a real ~/.nagioscli.ini (network, `pass` prompt).
  const savedHome = process.env.HOME;
  process.env.HOME = fs.mkdtempSync(path.join(os.tmpdir(), 'ncli-home-'));
  t.after(() => {
    process.env.HOME = savedHome;
  });
  stub.folders = [{ uri: vscode.Uri.file('/nonexistent-nagioscli-ws') }];
  const missing = activate({ subscriptions: [] });
  t.after(() => missing.timer && clearInterval(missing.timer));
  await missing.refresh();
  assert.match((await roots(missing))[0].text, /No nagioscli.ini found/);

  // A workspace ini pointing at a closed port: the real NagiosApi is built
  // and its connection error lands in the tree and in the detail document.
  const ws = fs.mkdtempSync(path.join(os.tmpdir(), 'ncli-ws-'));
  fs.writeFileSync(
    path.join(ws, 'nagioscli.ini'),
    '[nagios]\nurl = http://127.0.0.1:1/nagios\nusername = a\n[auth]\nmethod = nginx_token\nnginx_token = t\n',
  );
  stub.folders = [{ uri: vscode.Uri.file(ws) }];
  const controller = activate({ subscriptions: [] });
  t.after(() => controller.timer && clearInterval(controller.timer));
  await controller.refresh();
  assert.match((await roots(controller))[0].text, /connection error: .*ECONNREFUSED/);
  const provider = stub.docProviders.get('nagioscli-status');
  const uri = vscode.Uri.from({ scheme: 'nagioscli-status', path: '/h.log', query: 'host=h' });
  assert.match(await provider.provideTextDocumentContent(uri), /cannot load h: .*ECONNREFUSED/);
});
