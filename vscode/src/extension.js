// @ts-check
// VS Code glue: sidebar tree of the Nagios state read from nagioscli.ini —
// host problems, service problems, every host with its services — a
// read-only detail document per host / service (refreshed with the tree),
// "Force check", "Acknowledge" and "Open in Nagios" (ken #1132).

const vscode = require('vscode');
const { loadConfig } = require('./config');
const { NagiosApi } = require('./api');
const {
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
  stateIcon,
} = require('./status');

const SCHEME = 'nagioscli-status';
const GROUP_LABELS = {
  hosts: 'Host problems',
  services: 'Service problems',
  all: 'All hosts',
};

/** @typedef {import('./api').Host} Host */
/** @typedef {import('./api').Service} Service */
/** @typedef {import('./config').NagiosConfig} NagiosConfig */
/**
 * @typedef {{ kind: 'group', key: 'hosts', items: Host[] }
 *   | { kind: 'group', key: 'services', items: Service[] }
 *   | { kind: 'group', key: 'all', items: Host[] }
 *   | { kind: 'host', host: Host, scope: 'problem' | 'all' }
 *   | { kind: 'service', service: Service, scope: 'problem' | 'all' }
 *   | { kind: 'message', text: string }} Node
 */
/**
 * @typedef {object} Deps
 * @property {(dir: string) => NagiosConfig} loadConfig
 * @property {(cfg: NagiosConfig) => NagiosApi} makeApi
 * @property {() => Date} now
 */
/**
 * @typedef {object} Snapshot
 * @property {Host[]} hostProblems
 * @property {Service[]} serviceProblems
 * @property {Host[]} hosts
 */

/** @type {Deps} */
const DEFAULT_DEPS = {
  loadConfig: (dir) => loadConfig(dir),
  makeApi: (cfg) => new NagiosApi(cfg),
  now: () => new Date(),
};

/**
 * @param {unknown} err
 * @returns {string}
 */
function errorText(err) {
  return err instanceof Error ? err.message : String(err);
}

/**
 * Host / service carried by a detail document URI
 * (`nagioscli-status:/<label>.log?host=…&service=…`).
 * @param {vscode.Uri} uri
 * @returns {{ host: string, service: string | undefined } | null}
 */
function targetOf(uri) {
  const query = new URLSearchParams(uri.query);
  const host = query.get('host');
  if (!host) return null;
  return { host, service: query.get('service') ?? undefined };
}

/**
 * Host + optional service of a tree node, or null for other nodes.
 * @param {Node | undefined} node
 * @returns {{ host: string, service: string | undefined, label: string } | null}
 */
function nodeTarget(node) {
  if (node?.kind === 'host')
    return { host: node.host.name, service: undefined, label: node.host.name };
  if (node?.kind === 'service') {
    const { host_name: host, description: service } = node.service;
    return { host, service, label: `${host} / ${service}` };
  }
  return null;
}

/** @implements {vscode.TreeDataProvider<Node>} */
class StatusTreeProvider {
  /** @param {Deps} deps */
  constructor(deps) {
    this.deps = deps;
    /** @type {vscode.EventEmitter<Node | undefined>} */
    this.emitter = new vscode.EventEmitter();
    this.onDidChangeTreeData = this.emitter.event;
    /** @type {NagiosApi | null} */
    this.api = null;
    /** @type {Snapshot | null} */
    this.snapshot = null;
    /** @type {string | null} */
    this.error = null;
  }

  /**
   * The API for the current nagioscli.ini, rebuilt only when the config
   * changed: credentials (a `pass` call may prompt) are resolved once.
   * @param {string} dir
   * @returns {NagiosApi}
   */
  apiFor(dir) {
    const cfg = this.deps.loadConfig(dir);
    if (!this.api || JSON.stringify(this.api.cfg) !== JSON.stringify(cfg)) {
      this.api = this.deps.makeApi(cfg);
    }
    return this.api;
  }

  /** Reload the config (picks up nagioscli.ini edits) and the state. */
  async reload() {
    this.error = null;
    const folder = vscode.workspace.workspaceFolders?.[0];
    try {
      if (!folder) throw new Error('Open a folder that contains a nagioscli.ini.');
      const api = this.apiFor(folder.uri.fsPath);
      const [hostProblems, serviceProblems, hosts] = await Promise.all([
        api.listHostProblems(),
        api.listServiceProblems(),
        api.listHosts(),
      ]);
      this.snapshot = {
        hostProblems: sortHostProblems(hostProblems.filter(isHostProblem)),
        serviceProblems: sortServiceProblems(serviceProblems.filter(isServiceProblem)),
        hosts: [...hosts].sort((a, b) => a.name.localeCompare(b.name)),
      };
    } catch (err) {
      this.snapshot = null;
      this.error = errorText(err);
    }
    this.emitter.fire(undefined);
  }

  /** @returns {boolean} */
  get hideHandled() {
    return vscode.workspace.getConfiguration('nagioscli').get('hideHandled', false);
  }

  /** @returns {number} problems nobody has acknowledged or scheduled downtime for */
  get unhandledCount() {
    if (!this.snapshot) return 0;
    const { hostProblems, serviceProblems } = this.snapshot;
    return [...hostProblems, ...serviceProblems].filter((row) => !isHandled(row)).length;
  }

  /**
   * @param {Node} node
   * @returns {vscode.TreeItem}
   */
  getTreeItem(node) {
    if (node.kind === 'message') {
      const item = new vscode.TreeItem(node.text);
      item.iconPath = new vscode.ThemeIcon('warning');
      item.tooltip = node.text;
      return item;
    }
    if (node.kind === 'group') {
      const item = new vscode.TreeItem(
        GROUP_LABELS[node.key],
        node.key === 'all'
          ? vscode.TreeItemCollapsibleState.Collapsed
          : vscode.TreeItemCollapsibleState.Expanded,
      );
      item.id = `group:${node.key}`;
      item.description = String(node.items.length);
      return item;
    }
    return node.kind === 'host' ? this.hostItem(node) : this.serviceItem(node);
  }

  /**
   * @param {Extract<Node, { kind: 'host' }>} node
   * @returns {vscode.TreeItem}
   */
  hostItem(node) {
    const { host } = node;
    const state = hostState(host.status);
    const item = new vscode.TreeItem(
      host.name,
      node.scope === 'all'
        ? vscode.TreeItemCollapsibleState.Collapsed
        : vscode.TreeItemCollapsibleState.None,
    );
    item.id = `${node.scope}:host:${host.name}`;
    item.description = hostDescription(host, this.deps.now());
    this.decorate(item, node, state, host, isHostProblem(host));
    return item;
  }

  /**
   * @param {Extract<Node, { kind: 'service' }>} node
   * @returns {vscode.TreeItem}
   */
  serviceItem(node) {
    const { service } = node;
    const state = serviceState(service.status);
    const label =
      node.scope === 'problem'
        ? `${service.host_name} / ${service.description}`
        : service.description;
    const item = new vscode.TreeItem(label);
    item.id = `${node.scope}:service:${service.host_name}/${service.description}`;
    item.description = serviceDescription(service, this.deps.now());
    this.decorate(item, node, state, service, isServiceProblem(service));
    return item;
  }

  /**
   * Icon, tooltip, context value and click command shared by hosts and services.
   * @param {vscode.TreeItem} item
   * @param {Node} node
   * @param {string} state
   * @param {Host | Service} row
   * @param {boolean} problem
   */
  decorate(item, node, state, row, problem) {
    const [icon, color] = stateIcon(state, row);
    item.iconPath = new vscode.ThemeIcon(icon, color ? new vscode.ThemeColor(color) : undefined);
    const output = row.plugin_output ? `\n\n\`${row.plugin_output}\`` : '';
    item.tooltip = new vscode.MarkdownString(`**${item.label}**\n\n${item.description}${output}`);
    const kind = node.kind === 'host' ? 'host' : 'service';
    let health = 'ok';
    if (problem) health = isHandled(row) ? 'handled' : 'problem';
    item.contextValue = `${kind}.${health}`;
    item.command = { command: 'nagioscli.showStatus', title: 'Show status', arguments: [node] };
  }

  /**
   * @param {Node} [node]
   * @returns {Promise<Node[]>}
   */
  async getChildren(node) {
    if (!node) return this.roots();
    if (node.kind === 'group') return this.groupChildren(node);
    if (node.kind !== 'host' || node.scope !== 'all' || !this.api) return [];
    try {
      const services = await this.api.listHostServices(node.host.name);
      return [...services]
        .sort((a, b) => a.description.localeCompare(b.description))
        .map((service) => ({ kind: 'service', service, scope: 'all' }));
    } catch (err) {
      return [{ kind: 'message', text: errorText(err) }];
    }
  }

  /** @returns {Node[]} */
  roots() {
    if (this.error) return [{ kind: 'message', text: this.error }];
    if (!this.snapshot) return [];
    const keep = (/** @type {Host | Service} */ row) => !(this.hideHandled && isHandled(row));
    return [
      { kind: 'group', key: 'hosts', items: this.snapshot.hostProblems.filter(keep) },
      { kind: 'group', key: 'services', items: this.snapshot.serviceProblems.filter(keep) },
      { kind: 'group', key: 'all', items: this.snapshot.hosts },
    ];
  }

  /**
   * @param {Extract<Node, { kind: 'group' }>} node
   * @returns {Node[]}
   */
  groupChildren(node) {
    if (node.key === 'services') {
      return node.items.map((service) => ({ kind: 'service', service, scope: 'problem' }));
    }
    const scope = node.key === 'all' ? 'all' : 'problem';
    return node.items.map((host) => ({ kind: 'host', host, scope }));
  }
}

/**
 * Read-only `nagioscli-status:` documents, re-rendered on every refresh
 * (a Nagios state is never final).
 * @implements {vscode.TextDocumentContentProvider}
 */
class StatusDocumentProvider {
  /**
   * @param {StatusTreeProvider} tree
   * @param {Deps} deps
   */
  constructor(tree, deps) {
    this.tree = tree;
    this.deps = deps;
    /** @type {vscode.EventEmitter<vscode.Uri>} */
    this.emitter = new vscode.EventEmitter();
    this.onDidChange = this.emitter.event;
  }

  /**
   * @param {vscode.Uri} uri
   * @returns {Promise<string>}
   */
  async provideTextDocumentContent(uri) {
    const target = targetOf(uri);
    const { api } = this.tree;
    if (!target || !api) return 'nagioscli: nothing to show (refresh the Nagios view).\n';
    const { host, service } = target;
    const now = this.deps.now();
    try {
      if (service === undefined) {
        return hostDetailText(await api.getHost(host), api.webUrl(host), now);
      }
      const svc = await api.getService(host, service);
      return serviceDetailText(svc, api.webUrl(host, service), now);
    } catch (err) {
      const name = service === undefined ? host : `${host} / ${service}`;
      return `nagioscli: cannot load ${name}: ${errorText(err)}\n`;
    }
  }

  /** Re-render every open detail document. */
  refreshOpen() {
    for (const doc of vscode.workspace.textDocuments) {
      if (doc.uri.scheme === SCHEME) this.emitter.fire(doc.uri);
    }
  }
}

/** Wires the view, documents and commands; `deps` are swapped in tests. */
class Controller {
  /**
   * @param {vscode.ExtensionContext} context
   * @param {Deps} deps
   */
  constructor(context, deps) {
    this.context = context;
    this.tree = new StatusTreeProvider(deps);
    this.docs = new StatusDocumentProvider(this.tree, deps);
    this.view = vscode.window.createTreeView('nagioscli.status', { treeDataProvider: this.tree });
    /** @type {ReturnType<typeof setInterval> | null} */
    this.timer = null;
  }

  /** Tree + open detail documents, both reloaded from Nagios. */
  async refresh() {
    await this.tree.reload();
    const count = this.tree.unhandledCount;
    this.view.badge = count
      ? { value: count, tooltip: `${count} unhandled problem${count > 1 ? 's' : ''}` }
      : undefined;
    const cfg = this.tree.snapshot ? this.tree.api?.cfg : undefined;
    this.view.description = cfg ? new URL(cfg.url).host : undefined;
    this.docs.refreshOpen();
  }

  /** (Re)arm the periodic refresh from the `nagioscli.autoRefreshSeconds` setting. */
  armTimer() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    const seconds = vscode.workspace.getConfiguration('nagioscli').get('autoRefreshSeconds', 60);
    if (seconds > 0) {
      this.timer = setInterval(() => {
        if (vscode.window.state.focused) void this.refresh();
      }, seconds * 1000);
    }
  }

  /** @param {Node} node */
  async showStatus(node) {
    const target = nodeTarget(node);
    if (!target) return;
    const query = new URLSearchParams({ host: target.host });
    if (target.service !== undefined) query.set('service', target.service);
    const uri = vscode.Uri.from({
      scheme: SCHEME,
      path: `/${target.label.replaceAll('/', '_')}.log`,
      query: query.toString(),
    });
    const doc = await vscode.workspace.openTextDocument(uri);
    await vscode.languages.setTextDocumentLanguage(doc, 'log');
    await vscode.window.showTextDocument(doc, { preview: true });
  }

  /** @param {Node} [node] */
  openInBrowser(node) {
    const { api } = this.tree;
    if (!api) return;
    const target = nodeTarget(node);
    void vscode.env.openExternal(vscode.Uri.parse(api.webUrl(target?.host, target?.service)));
  }

  /**
   * Run a cmd.cgi action, report it, then refresh.
   * @param {string} done status bar text on success
   * @param {(api: NagiosApi) => Promise<void>} action
   */
  async runCommand(done, action) {
    const { api } = this.tree;
    if (!api) return;
    try {
      await action(api);
      vscode.window.setStatusBarMessage(`nagioscli: ${done}`, 3000);
    } catch (err) {
      void vscode.window.showErrorMessage(`nagioscli: ${errorText(err)}`);
    }
    await this.refresh();
  }

  /**
   * Force an immediate check (cmd.cgi 7 for a service, 96 for a host).
   * @param {Node} node
   */
  async forceCheck(node) {
    const target = nodeTarget(node);
    if (!target) return;
    await this.runCommand(`check of ${target.label} scheduled`, (api) =>
      api.forceCheck(target.host, target.service),
    );
  }

  /**
   * Acknowledge a problem with a comment (sticky, notifies, like `nagioscli ack`).
   * @param {Node} node
   */
  async acknowledge(node) {
    const target = nodeTarget(node);
    if (!target || !this.tree.api) return;
    const comment = await vscode.window.showInputBox({
      title: `Acknowledge ${target.label}`,
      prompt: 'Comment (sticky acknowledgement, contacts are notified)',
      ignoreFocusOut: true,
      validateInput: (value) => (value.trim() ? null : 'A comment is required'),
    });
    if (!comment?.trim()) return;
    await this.runCommand(`${target.label} acknowledged`, (api) =>
      api.acknowledge(target.host, target.service, comment.trim()),
    );
  }

  register() {
    const cmd = vscode.commands.registerCommand;
    this.context.subscriptions.push(
      this.view,
      vscode.workspace.registerTextDocumentContentProvider(SCHEME, this.docs),
      cmd('nagioscli.refresh', () => this.refresh()),
      cmd('nagioscli.openNagios', () => this.openInBrowser()),
      cmd('nagioscli.openInNagios', (/** @type {Node} */ node) => this.openInBrowser(node)),
      cmd('nagioscli.showStatus', (/** @type {Node} */ node) => this.showStatus(node)),
      cmd('nagioscli.forceCheck', (/** @type {Node} */ node) => this.forceCheck(node)),
      cmd('nagioscli.acknowledge', (/** @type {Node} */ node) => this.acknowledge(node)),
      vscode.workspace.onDidChangeWorkspaceFolders(() => this.refresh()),
      vscode.workspace.onDidChangeConfiguration((e) => {
        if (e.affectsConfiguration('nagioscli')) {
          this.armTimer();
          void this.refresh();
        }
      }),
      { dispose: () => this.timer && clearInterval(this.timer) },
    );
    this.armTimer();
    return this.refresh();
  }
}

/**
 * @param {vscode.ExtensionContext} context
 * @param {Deps} [deps]
 * @returns {Controller}
 */
function activate(context, deps = DEFAULT_DEPS) {
  const controller = new Controller(context, deps);
  void controller.register();
  return controller;
}

function deactivate() {}

module.exports = { activate, deactivate, nodeTarget, targetOf };
