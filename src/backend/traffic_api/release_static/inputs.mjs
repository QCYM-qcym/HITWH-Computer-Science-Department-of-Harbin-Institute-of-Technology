/* Versioned display consumer: saved fields only, without numerical replay. */
const ENDPOINT = '/release/v1/input-summary';
const BYTE_LIMIT = 65536;
const DEADLINE_MS = 10000;
const mounts = new WeakMap();
const POLICIES = ['P_U', 'P_B', 'P_A'];
const MINUTES = [
  ['total', '登记分钟'], ['raw_valid', '原始有效分钟'], ['prepared_valid', '预处理有效分钟'],
  ['common_valid', '共同有效分钟'], ['history_h15_valid', 'H15 历史有效分钟'],
  ['history_h30_valid', 'H30 历史有效分钟'],
];
const QUALIFICATIONS = [
  ['train_full_history_normal', '完整历史训练正常分钟'],
  ['calibration_full_history_normal', '完整历史校准正常分钟'],
  ['validation_current_normal', '验证当前正常分钟'],
  ['validation_current_attack', '验证当前攻击分钟'],
  ['validation_current_unknown', '验证当前未知分钟'],
  ['test_current_normal', '测试当前正常分钟'],
  ['test_current_attack', '测试当前攻击分钟'],
  ['test_current_unknown', '测试当前未知分钟'],
];
const CHECKS = {
  status: 'INTERNAL_CONSISTENCY_CHECKED', scope: 'SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY',
  byte_integrity: 'CHECKED', structure: 'CHECKED', upstream_replay: 'NOT_PERFORMED',
  transform_history_replay: 'NOT_PERFORMED', fit_parameters: 'NOT_REESTIMATED',
};
const CHECK_LABELS = {
  status: '检查状态', scope: '检查范围', byte_integrity: '字节完整性', structure: '保存结构',
  upstream_replay: '上游重放', transform_history_replay: '变换与历史重放', fit_parameters: '拟合参数',
};
class ViewError extends Error {
  constructor(code) { super(code); this.code = code; }
}
function need(condition) { if (!condition) throw new ViewError('INVALID_SHAPE'); }
function keys(value, names) {
  need(value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name)));
}
function count(value, minimum = 0) {
  need(Number.isSafeInteger(value) && value >= minimum && value <= 10000);
}
function sha(value) { need(typeof value === 'string' && value.length === 64 && /^[a-f0-9]{64}$/.test(value)); }
function identity(value, profile) {
  keys(value, ['profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count']);
  need(value.profile_id === profile);
  sha(value.context_sha256); sha(value.manifest_sha256);
  need(Number.isSafeInteger(value.manifest_byte_count) && value.manifest_byte_count > 0);
}
function validate(value) {
  keys(value, ['version', 'command', 'status', 'summary', 'replay']);
  need(value.version === 1 && value.command === 'inspect'
    && value.status === CHECKS.status && value.replay === null);
  const s = value.summary;
  keys(s, ['identity', 'upstream_identity', 'source_authentication', 'time_basis', 'configuration',
    'configuration_sha256', 'minute_counts', 'fit', 'qualification_counts', 'package_checks']);
  identity(s.identity, 'c17-release-prepared-input-package-v1');
  identity(s.upstream_identity, 'c17-release-minute-package-v1');
  need(s.source_authentication === 'NOT_AUTHENTICATED' && s.time_basis === 'SOURCE_WALL_CLOCK_COMPLETION_PROXY');
  const c = s.configuration;
  keys(c, ['schema_version', 'numeric_rules_id', 'windows', 'fit_window', 'epsilon',
    'audit_fit_policy', 'policy_status', 'feature_count']);
  need(c.schema_version === 1 && c.numeric_rules_id === 'c17-release-log1p-mad-input-rules-v1'
    && Array.isArray(c.windows) && c.windows.length === 2 && c.windows[0] === 15 && c.windows[1] === 30
    && c.fit_window === 30 && c.feature_count === 13 && POLICIES.includes(c.audit_fit_policy)
    && c.policy_status === 'AUDIT_ONLY' && typeof c.epsilon === 'number'
    && Number.isFinite(c.epsilon) && c.epsilon > 0);
  sha(s.configuration_sha256);
  keys(s.minute_counts, MINUTES.map(([name]) => name));
  for (const [name] of MINUTES) count(s.minute_counts[name], name === 'total' ? 1 : 0);
  keys(s.fit, ['count', 'mask_sha256', 'rows_sha256']);
  count(s.fit.count); sha(s.fit.mask_sha256); sha(s.fit.rows_sha256);
  keys(s.qualification_counts, POLICIES);
  for (const policy of POLICIES) {
    keys(s.qualification_counts[policy], QUALIFICATIONS.map(([name]) => name));
    for (const [name] of QUALIFICATIONS) count(s.qualification_counts[policy][name]);
  }
  keys(s.package_checks, Object.keys(CHECKS));
  for (const [name, expected] of Object.entries(CHECKS)) need(s.package_checks[name] === expected);
  return s;
}
function node(tag, text, className) {
  const result = document.createElement(tag);
  if (text !== undefined) result.textContent = String(text);
  if (className) result.className = className;
  return result;
}
function pair(list, label, value, code = false) {
  list.append(node('dt', label));
  const entry = node('dd'); entry.append(node(code ? 'code' : 'span', value)); list.append(entry);
}
function section(title, description) {
  const result = node('section', undefined, 'panel'); result.append(node('h2', title));
  if (description) result.append(node('p', description, 'muted'));
  return result;
}
function identityPanel(title, value) {
  const result = section(title), list = node('dl', undefined, 'facts');
  pair(list, '包协议', value.profile_id, true);
  pair(list, '清单字节数', value.manifest_byte_count);
  result.append(list);
  const details = node('details'); details.append(node('summary', '查看完整 SHA'));
  const hashes = node('dl', undefined, 'facts');
  pair(hashes, '上下文 SHA256', value.context_sha256, true);
  pair(hashes, '清单 SHA256', value.manifest_sha256, true);
  details.append(hashes); result.append(details);
  return result;
}
function renderSummary(content, s) {
  const fragment = document.createDocumentFragment();
  const identities = node('div', undefined, 'identity-grid');
  identities.append(identityPanel('输入包身份', s.identity), identityPanel('上游分钟包身份', s.upstream_identity));
  fragment.append(identities);
  const population = section('保存的分钟数量', '以下是保存掩码的计数，未进行页面抽样或重新评价。');
  const cards = node('div', undefined, 'count-grid');
  for (const [key, label] of MINUTES) {
    const card = node('div', undefined, 'count-card'), number = node('strong', s.minute_counts[key]);
    number.dataset.count = key; card.append(node('span', label), number); cards.append(card);
  }
  population.append(cards); fragment.append(population);
  const fit = section('保存的拟合记录', '这是预处理记录中保存的用于拟合的分钟数，不据此判断模型就绪。');
  const fitRow = node('p', undefined, 'fit-row'), fitCount = node('strong', s.fit.count);
  fitCount.dataset.fitCount = '';
  fitRow.append(node('span', '保存的拟合分钟数 '), fitCount,
    node('span', `保存的审计拟合政策 ${s.configuration.audit_fit_policy}`, 'badge'));
  fit.append(fitRow);
  const fitDetails = node('details'); fitDetails.append(node('summary', '查看保存的拟合标识'));
  const fitHashes = node('dl', undefined, 'facts');
  pair(fitHashes, '拟合掩码 SHA256', s.fit.mask_sha256, true);
  pair(fitHashes, '拟合行 SHA256', s.fit.rows_sha256, true);
  fitDetails.append(fitHashes); fit.append(fitDetails); fragment.append(fit);
  const qualifications = section('符合条件的分钟数', '三列仅作并列审计，不切换拟合政策、不进行排名。');
  const region = node('div', undefined, 'table-region'); region.id = 'input-qualifications';
  region.tabIndex = 0; region.setAttribute('role', 'region');
  region.setAttribute('aria-label', '三种政策下符合条件的分钟数，可横向滚动');
  const table = node('table'); table.append(node('caption', '按保存的审计政策列示资格分钟数'));
  const head = node('thead'), header = node('tr');
  for (const label of ['符合条件的分钟数', ...POLICIES]) {
    const cell = node('th', label); cell.scope = 'col'; header.append(cell);
  }
  head.append(header); table.append(head);
  const body = node('tbody');
  for (const [key, label] of QUALIFICATIONS) {
    const row = node('tr'), heading = node('th', label); heading.scope = 'row'; row.append(heading);
    for (const policy of POLICIES) {
      const cell = node('td', s.qualification_counts[policy][key]);
      cell.dataset.policy = policy; cell.dataset.qualification = key; row.append(cell);
    }
    body.append(row);
  }
  table.append(body); region.append(table); qualifications.append(region);
  qualifications.append(node('p', '0 只表示符合该条件的分钟数为零；零校准不表示评价比率为零。', 'notice'));
  fragment.append(qualifications);
  const configuration = section('窗口与数值配置');
  const details = node('details'); details.append(node('summary', '展开保存的配置'));
  const list = node('dl', undefined, 'facts');
  pair(list, '配置版本', s.configuration.schema_version);
  pair(list, '特征数', s.configuration.feature_count);
  pair(list, '历史窗口', s.configuration.windows.join(' / '));
  pair(list, '拟合窗口', s.configuration.fit_window);
  pair(list, 'epsilon', s.configuration.epsilon);
  pair(list, '数值规则', s.configuration.numeric_rules_id, true);
  pair(list, '配置 SHA256', s.configuration_sha256, true);
  details.append(list); configuration.append(details); fragment.append(configuration);
  const checks = section('检查范围与限定', '仅检查保存内容的内部一致性；本次未重放上游或变换与历史，未重估拟合参数。');
  checks.append(node('p', '来源未认证；时间按源钟面完成代理展示（非认证 UTC），不把源钟面视作 UTC。审计政策不构成研究许可。', 'notice'));
  const badges = node('div', undefined, 'badges');
  for (const value of [s.source_authentication, s.time_basis, s.configuration.policy_status]) badges.append(node('code', value, 'badge'));
  checks.append(badges);
  const checkList = node('dl', undefined, 'facts');
  for (const [key, value] of Object.entries(s.package_checks)) pair(checkList, CHECK_LABELS[key], value, true);
  checks.append(checkList); fragment.append(checks);
  content.replaceChildren(fragment); content.hidden = false;
}
function waitFor(promise, signal) {
  return new Promise((resolve, reject) => {
    let finished = false;
    const finish = (handler, value) => {
      if (finished) return;
      finished = true; signal.removeEventListener('abort', abort); handler(value);
    };
    const abort = () => finish(reject, new ViewError('CANCELLED'));
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) abort();
    Promise.resolve(promise).then(value => finish(resolve, value), error => finish(reject, error));
  });
}

export function mountReleaseInputView(root, { fetchImpl = globalThis.fetch.bind(globalThis) } = {}) {
  if (mounts.has(root)) return mounts.get(root);
  const heading = node('header', undefined, 'page-heading');
  heading.append(node('p', 'RELEASE · 保存的输入摘要', 'eyebrow'), node('h1', '输入包检查'),
    node('p', '查看一个输入包的身份、分钟资格与检查范围。', 'muted'));
  const status = node('p', '正在读取输入包摘要…', 'status'); status.id = 'input-status';
  status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const errorBox = node('p', '', 'error'); errorBox.id = 'input-error'; errorBox.hidden = true;
  errorBox.setAttribute('role', 'alert');
  const content = node('div'); content.id = 'input-content'; content.hidden = true;
  root.replaceChildren(heading, status, errorBox, content);
  const controller = new AbortController();
  const deadline = performance.now() + DEADLINE_MS;
  let destroyed = false, settled = false, timer, reader = null, responseBody = null, cancelled = false;
  function cleanup() {
    clearTimeout(timer); window.removeEventListener('pagehide', destroy);
  }
  function cancelReader() {
    if (cancelled) return;
    cancelled = true;
    const target = reader ?? responseBody;
    if (target && typeof target.cancel === 'function') {
      try { Promise.resolve(target.cancel()).catch(() => {}); } catch { /* cancellation is best effort */ }
    }
  }
  function showError(message) {
    content.replaceChildren(); content.hidden = true;
    errorBox.textContent = message; errorBox.hidden = false;
    status.textContent = '未能读取输入包摘要。'; root.dataset.state = 'error';
  }
  function destroy() {
    if (destroyed) return;
    destroyed = true; controller.abort(); cancelReader(); cleanup();
  }
  function expire() {
    if (destroyed || settled) return;
    settled = true; controller.abort(); cancelReader(); cleanup();
    showError('读取超时（10秒），请重新打开页面。');
  }
  function requireActive() {
    if (destroyed || settled) throw new ViewError('CANCELLED');
    if (performance.now() >= deadline) {
      expire(); throw new ViewError('CANCELLED');
    }
  }
  timer = setTimeout(expire, DEADLINE_MS);
  window.addEventListener('pagehide', destroy, { once: true });
  root.dataset.state = 'loading';
  const handle = Object.freeze({ destroy }); mounts.set(root, handle);
  async function load() {
    try {
      const response = await waitFor(fetchImpl(ENDPOINT, { method: 'GET', headers: { Accept: 'application/json' },
        cache: 'no-store', credentials: 'same-origin', redirect: 'error', signal: controller.signal }), controller.signal);
      responseBody = response?.body;
      requireActive();
      if (response?.status !== 200) throw new ViewError('FETCH_FAILED');
      const media = response.headers?.get('Content-Type')?.split(';', 1)[0].trim().toLowerCase();
      need(media === 'application/json' && responseBody && typeof responseBody.getReader === 'function');
      reader = responseBody.getReader();
      need(reader && typeof reader.read === 'function');
      const chunks = []; let total = 0;
      try {
        while (true) {
          const part = await waitFor(reader.read(), controller.signal);
          requireActive();
          if (part.done) break;
          need(ArrayBuffer.isView(part.value) && Object.prototype.toString.call(part.value) === '[object Uint8Array]');
          total += part.value.byteLength;
          if (total > BYTE_LIMIT) throw new ViewError('RESOURCE_LIMIT');
          chunks.push(new Uint8Array(part.value));
        }
      } catch (error) {
        cancelReader(); throw error;
      } finally {
        if (reader && typeof reader.releaseLock === 'function') {
          try { reader.releaseLock(); } catch { /* a cancelled host reader can already be released */ }
        }
        reader = null;
      }
      const payload = new Uint8Array(total); let offset = 0;
      for (const chunk of chunks) { payload.set(chunk, offset); offset += chunk.byteLength; }
      let parsed;
      try { parsed = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(payload)); }
      catch { throw new ViewError('INVALID_SHAPE'); }
      const summary = validate(parsed);
      requireActive();
      renderSummary(content, summary);
      status.textContent = '已读取保存的内部检查摘要。'; root.dataset.state = 'ready';
      settled = true; cleanup();
    } catch (error) {
      if (destroyed || settled) return;
      settled = true; controller.abort(); cancelReader(); cleanup();
      const code = error instanceof ViewError ? error.code : 'FETCH_FAILED';
      showError(code === 'RESOURCE_LIMIT' ? '响应超出读取上限，未显示摘要。'
        : code === 'INVALID_SHAPE' ? '响应格式不匹配，未显示摘要。' : '读取失败，请重新打开页面。');
    }
  }
  void load();
  return handle;
}

if (typeof document !== 'undefined') {
  const root = document.querySelector('[data-release-input-view]');
  if (root) mountReleaseInputView(root);
}
