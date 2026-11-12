/* Saved declarations only; no model, source discovery or numerical replay. */
import { validateSummary as validateResultSummary } from '/release/results/results.mjs';

const VIEWS = ['current13', 'h30_26'];
const PROFILE = 'c17-release-iforest-learned-view-v1';
const SCOPE = 'REGISTERED_SAVED_LEARNED_TUPLE_INSPECTION_ONLY';
const BASE = ['completed_source_record_count', 'fwd_packet_sum', 'bwd_packet_sum', 'fwd_source_length_sum',
  'bwd_source_length_sum', 'tcp_source_record_count', 'udp_source_record_count', 'known_other_source_protocol_record_count',
  'unresolved_source_protocol_record_count', 'duration_max_s', 'duration_median_s', 'duration_p95_s', 'no_backward_packet_source_record_count'];
const REFERENCES = { raw: 'c17-release-minute-package-v1', prepared: 'c17-release-prepared-input-package-v1',
  result: 'c17-release-iforest-result-package-v1', learned: 'c17-release-iforest-learned-package-v1' };
const ID_FIELDS = ['profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count'];
const CONFIG = ['input_width', 'n_estimators', 'max_samples', 'max_features', 'bootstrap', 'contamination', 'random_state', 'n_jobs'];
const COUNTS = ['total', 'training', 'calibration', 'preprocessing_fit'];
const CHECKS = { byte_integrity: 'MATCHED', structure: 'MATCHED', numerical_replay: 'NOT_RUN',
  input_pair_binding: 'NOT_PERFORMED', result_binding: 'NOT_PERFORMED', source_authentication: 'NOT_AUTHENTICATED', model_origin: 'NOT_AUTHENTICATED' };
const REGISTRATION = { input_pair_binding: 'MATCHED', result_pair_binding: 'MATCHED', learned_declarations_binding: 'MATCHED' };
const LIMITS = { metadata_bytes: 65536, source_axis_minutes: 10000, result_page_size: 100, result_page_bytes: 131072 };
const ERROR_TEXT = { INVALID_SHAPE: '摘要格式不符合约定。', IDENTITY_MISMATCH: '两个摘要的保存身份或总体不一致。',
  SNAPSHOT_MISMATCH: '摘要快照核对未通过。', RESOURCE_LIMIT: '摘要超过读取上限。', FETCH_FAILED: '未能读取保存摘要。',
  TIMEOUT: '读取或核对已超时。', CRYPTO_UNAVAILABLE: '当前环境无法核对摘要快照。', VIEW_UNAVAILABLE: '暂时无法显示保存摘要。' };
const STALE = Symbol('inactive learned view attempt');
const mounts = new WeakMap();
const ownedErrors = new WeakMap();
class ViewError extends Error { constructor(code) { super(code); this.code = code; ownedErrors.set(this, code); } }
function need(condition, code = 'INVALID_SHAPE') { if (!condition) throw new ViewError(code); }
function keys(value, names) {
  need(value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name)));
}
function integer(value, lower = 0, upper = 10000) {
  need(Number.isSafeInteger(value) && !Object.is(value, -0) && value >= lower && value <= upper);
}
function sha(value) { need(typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)); }
function reference(value, kind) {
  keys(value, ID_FIELDS); need(value.profile_id === REFERENCES[kind]); sha(value.context_sha256); sha(value.manifest_sha256);
  integer(value.manifest_byte_count, 1, kind === 'learned' ? 8192 : 65536);
}
function sameReference(a, b) { return ID_FIELDS.every(field => a[field] === b[field]); }
function sameConfiguration(a, b) { return CONFIG.every(field => a[field] === b[field]); }
function binding(condition) { need(condition, 'IDENTITY_MISMATCH'); }

export function validateLearnedSummary(value, expectedView) {
  need(VIEWS.includes(expectedView));
  keys(value, ['version', 'profile_id', 'scope', 'learned_identity', 'view', 'input_references', 'result_reference', 'declarations', 'counts', 'checks']);
  need(value.version === 1 && value.profile_id === 'c17-release-iforest-learned-summary-v1'
    && value.scope === 'SAVED_LEARNED_INTERNAL_CONSISTENCY_ONLY' && value.view === expectedView);
  reference(value.learned_identity, 'learned'); reference(value.result_reference, 'result');
  keys(value.input_references, ['raw', 'prepared']); reference(value.input_references.raw, 'raw'); reference(value.input_references.prepared, 'prepared');
  const d = value.declarations, c = value.counts;
  keys(d, ['configuration_sha256', 'population_sha256', 'input_rules_id', 'feature_columns', 'model_configuration', 'fit_runtime_id']);
  sha(d.configuration_sha256); sha(d.population_sha256);
  need(d.input_rules_id === 'c17-release-log1p-mad-input-rules-v1'
    && d.fit_runtime_id === 'python314-numpy254-sklearn191-joblib160-serial-wm1024-v1');
  const columns = BASE.map(name => 'current:' + name).concat(expectedView === 'current13' ? [] : BASE.map(name => 'residual_h30:' + name));
  need(Array.isArray(d.feature_columns) && d.feature_columns.length === columns.length
    && columns.every((name, index) => d.feature_columns[index] === name));
  keys(c, [...COUNTS, 'trees', 'nodes']); for (const name of COUNTS) integer(c[name], 1);
  need(c.training <= c.preprocessing_fit && c.preprocessing_fit <= c.total && c.training + c.calibration <= c.total);
  const model = d.model_configuration; keys(model, CONFIG);
  for (const name of ['input_width', 'n_estimators', 'max_samples', 'random_state', 'n_jobs']) integer(model[name]);
  need(model.input_width === (expectedView === 'current13' ? 13 : 26) && model.n_estimators === 16
    && model.max_samples === Math.min(32, c.training) && typeof model.max_features === 'number' && model.max_features === 1
    && model.bootstrap === false && model.contamination === 'auto' && model.random_state === 42 && model.n_jobs === 1);
  integer(c.trees, 16, 16); integer(c.nodes, 16, 16 * (2 * model.max_samples - 1)); need(c.nodes % 2 === 0);
  keys(value.checks, Object.keys(CHECKS)); for (const [name, expected] of Object.entries(CHECKS)) need(value.checks[name] === expected);
  return value;
}
function validateEnvelope(value) {
  keys(value, ['version', 'profile_id', 'scope', 'snapshot_sha256', 'result_snapshot_sha256', 'input_references',
    'result_references', 'learned_references', 'populations', 'views', 'registration_checks', 'replay', 'limits']);
  need(value.version === 1 && value.profile_id === PROFILE && value.scope === SCOPE && value.replay === null);
  sha(value.snapshot_sha256); sha(value.result_snapshot_sha256);
  keys(value.input_references, ['raw', 'prepared']); reference(value.input_references.raw, 'raw'); reference(value.input_references.prepared, 'prepared');
  keys(value.result_references, VIEWS); keys(value.learned_references, VIEWS); keys(value.views, VIEWS);
  const p = value.populations; keys(p, ['total', 'common', 'unscored', 'test_total', 'test_common', 'training', 'calibration', 'preprocessing_fit']);
  for (const name of Object.keys(p)) integer(p[name], COUNTS.includes(name) ? 1 : 0);
  need(p.common + p.unscored === p.total && p.training + p.calibration <= p.common
    && p.training <= p.preprocessing_fit && p.preprocessing_fit <= p.total
    && p.test_common <= p.test_total && p.test_total <= p.total && p.test_common <= p.common);
  keys(value.registration_checks, Object.keys(REGISTRATION));
  for (const [name, expected] of Object.entries(REGISTRATION)) need(value.registration_checks[name] === expected);
  keys(value.limits, Object.keys(LIMITS)); for (const [name, expected] of Object.entries(LIMITS)) { integer(value.limits[name], 1, 131072); need(value.limits[name] === expected); }
  for (const view of VIEWS) {
    reference(value.result_references[view], 'result'); reference(value.learned_references[view], 'learned');
    const s = validateLearnedSummary(value.views[view], view);
    binding(sameReference(value.learned_references[view], s.learned_identity) && sameReference(value.result_references[view], s.result_reference)
      && sameReference(value.input_references.raw, s.input_references.raw) && sameReference(value.input_references.prepared, s.input_references.prepared)
      && COUNTS.every(name => s.counts[name] === p[name]));
  }
  binding(value.views.current13.declarations.configuration_sha256 === value.views.h30_26.declarations.configuration_sha256
    && value.views.current13.declarations.population_sha256 === value.views.h30_26.declarations.population_sha256);
  return value;
}
export function validateLearnedView(value, resultSummary) {
  validateEnvelope(value);
  try { validateResultSummary(resultSummary); } catch { throw new ViewError('INVALID_SHAPE'); }
  const p = value.populations, r = resultSummary;
  binding(sameReference(value.input_references.raw, r.input_references.raw) && sameReference(value.input_references.prepared, r.input_references.prepared)
    && value.result_snapshot_sha256 === r.snapshot_sha256 && p.total === r.axis.minute_count && p.common === r.axis.scored_count && p.unscored === r.axis.unscored_count);
  const test = r.axis.segments.filter(segment => segment.role === 'test');
  binding(p.test_total === test.reduce((sum, segment) => sum + segment.minute_count, 0)
    && p.test_common === test.reduce((sum, segment) => sum + segment.scored_count, 0));
  for (const view of VIEWS) {
    const s = value.views[view], old = r.views[view];
    binding(sameReference(value.result_references[view], r.result_references[view])
      && s.declarations.configuration_sha256 === r.input_references.configuration_sha256
      && sameConfiguration(s.declarations.model_configuration, old.configuration)
      && p.training === old.training_count && p.calibration === old.calibration_count && p.preprocessing_fit === old.preprocessing_fit_count);
  }
  return value;
}
function canonical(value, path = [], omitSnapshot = false) {
  if (Array.isArray(value)) return '[' + value.map((item, index) => canonical(item, [...path, String(index)], omitSnapshot)).join(',') + ']';
  if (value !== null && typeof value === 'object') return '{' + Object.keys(value).sort()
    .filter(name => !(omitSnapshot && path.length === 0 && name === 'snapshot_sha256'))
    .map(name => JSON.stringify(name) + ':' + canonical(value[name], [...path, name], omitSnapshot)).join(',') + '}';
  if (path.length === 5 && path[0] === 'views' && VIEWS.includes(path[1])
      && path.slice(2).join('.') === 'declarations.model_configuration.max_features') return '1.0';
  return JSON.stringify(value);
}
export function canonicalLearnedViewBytes(value) {
  validateEnvelope(value); return new TextEncoder().encode(canonical(value, [], true) + '\n');
}
function capture(value, resultSummary) {
  validateLearnedView(value, resultSummary);
  const newBytes = canonicalLearnedViewBytes(value);
  const oldBytes = new TextEncoder().encode(canonical({ ...resultSummary.result_references, profile_id: 'c17-release-iforest-view-v1' }) + '\n');
  const expected = [value.snapshot_sha256, resultSummary.snapshot_sha256];
  const subtle = globalThis.crypto?.subtle;
  need(subtle && typeof subtle.digest === 'function', 'CRYPTO_UNAVAILABLE');
  return { value, newBytes, oldBytes, expected, digest: subtle.digest.bind(subtle) };
}
async function verifyCaptured(saved, gate) {
  for (const [index, bytes] of [saved.newBytes, saved.oldBytes].entries()) {
    gate(); let result;
    try { result = await saved.digest('SHA-256', bytes); } catch { gate(); throw new ViewError('SNAPSHOT_MISMATCH'); }
    gate();
    const hash = Array.from(new Uint8Array(result), byte => byte.toString(16).padStart(2, '0')).join('');
    need(hash === saved.expected[index], 'SNAPSHOT_MISMATCH');
  }
  return saved.value;
}
// Callers keep public plain JSON values stable for this asynchronous operation.
export async function verifyLearnedView(value, resultSummary) { return verifyCaptured(capture(value, resultSummary), () => {}); }

function node(tag, text, className) {
  const item = document.createElement(tag); if (text !== undefined) item.textContent = String(text);
  if (className) item.className = className; return item;
}
function fact(list, label, text) { list.append(node('dt', label), node('dd', text)); }
function readyFragment(value, old) {
  const fragment = document.createDocumentFragment();
  fragment.append(node('p', '仅核对已提供包的保存声明；来源、历史模型和预处理派生未认证。', 'notice'),
    node('p', '本页未执行显式数值复算。replay = null；学习状态中的 NOT_RUN 与 NOT_PERFORMED 保持原义。', 'notice'));
  const population = node('section', undefined, 'panel'); population.append(node('h2', '全轴与测试分区'));
  const counts = node('dl', undefined, 'facts');
  for (const [name, label] of [['total', '全轴分钟'], ['common', '公共评分分钟'], ['unscored', '未评分分钟'], ['test_total', '完整测试分钟'],
    ['test_common', '测试公共评分分钟'], ['training', '模型训练分钟'], ['calibration', '独立校准分钟'], ['preprocessing_fit', '预处理拟合分钟']]) fact(counts, label, value.populations[name]);
  population.append(counts, node('p', '这些计数覆盖完整源分钟轴。role=train 不等于每行都用于训练；测试总数、公共分钟和校准分钟分别记录。', 'muted')); fragment.append(population);
  const cards = node('div', undefined, 'cards');
  const configLabels = { input_width: '输入维数', n_estimators: '树数', max_samples: '每棵树采样上限', max_features: '特征比例',
    bootstrap: '有放回采样', contamination: '模型污染参数', random_state: '随机种子', n_jobs: '并行任务数' };
  for (const view of VIEWS) {
    const s = value.views[view], card = node('section', undefined, 'panel'); card.dataset.viewCard = view;
    card.append(node('h2', view === 'current13' ? 'current13 · 当前 13 维' : 'H30_26 · 当前 13 维 + 历史残差 13 维'));
    const facts = node('dl', undefined, 'facts'); fact(facts, '保存的树数', s.counts.trees); fact(facts, '保存的节点总数', s.counts.nodes);
    for (const field of CONFIG) fact(facts, configLabels[field], s.declarations.model_configuration[field]); card.append(facts);
    const features = node('details'); features.append(node('summary', '查看完整特征顺序'));
    const list = node('ol', undefined, 'features'); for (const column of s.declarations.feature_columns) list.append(node('li', column)); features.append(list); card.append(features); cards.append(card);
  }
  fragment.append(cards, node('p', 'H30 历史基线采用前 30 分钟 [t−30,t)，不包含当前分钟 t。两个保存结果使用同一公共评分总体；页面不会重新计算历史特征。', 'muted'));
  const checks = node('section', undefined, 'panel'); checks.append(node('h2', '加载检查与注册声明'));
  checks.append(node('p', '注册 MATCHED 仅表示所提供的保存声明与输入对、结果相符，不代表预处理派生、数值复算或来源认证。'));
  const registration = node('dl', undefined, 'facts');
  const registrationLabels = { input_pair_binding: '注册输入对声明', result_pair_binding: '注册结果声明', learned_declarations_binding: '注册学习状态声明' };
  for (const [name, label] of Object.entries(registrationLabels)) fact(registration, label, value.registration_checks[name]); checks.append(registration);
  const labels = { byte_integrity: '保存字节检查', structure: '保存结构检查', numerical_replay: '数值复算', input_pair_binding: '学习包自带输入配对检查',
    result_binding: '学习包自带结果绑定检查', source_authentication: '来源认证', model_origin: '历史模型认证' };
  for (const view of VIEWS) {
    checks.append(node('h3', `${view} · 学习包原有检查`)); const list = node('dl', undefined, 'facts');
    for (const [name, label] of Object.entries(labels)) fact(list, label, value.views[view].checks[name]); checks.append(list);
  }
  fragment.append(checks);
  const identities = node('details', undefined, 'panel'); identities.append(node('summary', '查看完整身份、快照与声明范围'));
  const envelope = node('dl', undefined, 'facts'); fact(envelope, '展示范围', value.scope); fact(envelope, '学习展示快照 SHA256', value.snapshot_sha256);
  fact(envelope, '保存结果快照 SHA256', value.result_snapshot_sha256); fact(envelope, '来源钟面', old.source.time_basis);
  fact(envelope, '来源认证', old.source.authentication); fact(envelope, '政策状态', old.source.policy_status); fact(envelope, '审计拟合政策', old.source.audit_fit_policy);
  identities.append(envelope, node('p', '源钟面是完成时间代理，不是认证 UTC。快照哈希绑定保存声明，不认证来源或历史模型。', 'muted'));
  for (const [label, ref] of [['原始分钟包', value.input_references.raw], ['预处理输入包', value.input_references.prepared],
    ['current13 结果包', value.result_references.current13], ['H30_26 结果包', value.result_references.h30_26],
    ['current13 学习包', value.learned_references.current13], ['H30_26 学习包', value.learned_references.h30_26]]) {
    identities.append(node('h3', label)); const list = node('dl', undefined, 'facts');
    for (const field of ID_FIELDS) fact(list, field, ref[field]); identities.append(list);
  }
  for (const view of VIEWS) {
    const d = value.views[view].declarations, list = node('dl', undefined, 'facts'); identities.append(node('h3', `${view} · 声明`));
    for (const field of ['configuration_sha256', 'population_sha256', 'input_rules_id', 'fit_runtime_id']) fact(list, field, d[field]); identities.append(list);
  }
  fragment.append(identities);
  const link = node('a', '查看保存的双视图结果 →', 'result-link'); link.href = '/release/results'; fragment.append(link);
  return fragment;
}
function waitFor(promise, signal) {
  return new Promise((resolve, reject) => {
    let ended = false;
    function finish(action, value) { if (ended) return; ended = true; signal.removeEventListener('abort', aborted); action(value); }
    function aborted() { finish(reject, STALE); }
    signal.addEventListener('abort', aborted, { once: true });
    Promise.resolve(promise).then(value => finish(resolve, value), error => finish(reject, error));
    if (signal.aborted) aborted();
  });
}
export function mountReleaseIFLearnedView(root, {
  fetchImpl = globalThis.fetch.bind(globalThis), setTimeoutImpl = globalThis.setTimeout.bind(globalThis),
  clearTimeoutImpl = globalThis.clearTimeout.bind(globalThis), now = () => globalThis.performance.now(),
} = {}) {
  const existing = mounts.get(root); if (existing?.lifetime.live && !existing.lifetime.disposed) return existing.handle;
  const lifetime = { live: true, disposed: false, onDispose: null }; let destroyed = false, current = null;
  const title = node('h1', '学习状态包检查'), status = node('p', '', 'status'), error = node('p', '', 'error');
  status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite'); error.setAttribute('role', 'alert'); error.hidden = true;
  const content = node('div'), actions = node('div', undefined, 'actions'); root.replaceChildren(title, status, error, content, actions);
  function cancelSlot(slot) {
    if (slot.completed) return;
    const target = slot.reader ?? slot.body;
    if (!target || slot.cancelled.has(target)) return;
    slot.cancelled.add(target);
    try { if (typeof target.cancel === 'function') Promise.resolve(target.cancel()).catch(() => {}); } catch { /* best effort host cancellation */ }
  }
  function cancelAttempt(attempt) {
    if (!attempt || attempt.settled) return; attempt.settled = true;
    try { attempt.controller.abort(); } catch { /* continue independent body cancellation */ }
    for (const slot of attempt.slots) cancelSlot(slot);
    clearTimeoutImpl(attempt.timer);
  }
  function start() {
    if (destroyed || !owns()) return;
    const previous = current; cancelAttempt(previous);
    if (destroyed || !owns() || current !== previous) return;
    const attempt = { controller: new AbortController(), deadline: now() + 10000, settled: false, timer: null,
      slots: [0, 1].map(() => ({ body: null, reader: null, completed: false, cancelled: new Set() })) };
    current = attempt;
    const active = () => !destroyed && owns() && lifetime.live && current === attempt && !attempt.settled;
    function gate() { if (!active()) throw STALE; if (now() >= attempt.deadline) throw new ViewError('TIMEOUT'); }
    function fail(problem) {
      if (!active()) return;
      try { gate(); } catch (gated) { problem = gated; }
      if (!active()) return;
      // Only identities of errors created by this module are classified.
      const code = ownedErrors.get(problem) ?? 'VIEW_UNAVAILABLE';
      cancelAttempt(attempt); if (destroyed || !owns() || current !== attempt) return;
      content.replaceChildren(); actions.replaceChildren(); error.hidden = false; error.textContent = ERROR_TEXT[code]; root.dataset.errorCode = code;
      const retry = node('button', '重试读取两个摘要'); retry.type = 'button'; retry.dataset.action = 'retry'; actions.append(retry);
      root.dataset.state = 'error'; root.setAttribute('aria-busy', 'false'); status.textContent = '未能完成两个保存摘要的核对。';
    }
    root.dataset.state = 'loading'; root.setAttribute('aria-busy', 'true'); delete root.dataset.errorCode;
    content.replaceChildren(); actions.replaceChildren(); error.hidden = true; error.textContent = ''; status.textContent = '正在读取并核对两个保存摘要…';
    attempt.timer = setTimeoutImpl(() => fail(new ViewError('TIMEOUT')), 10000);
    async function transport(thunk) {
      gate(); let result;
      try { result = await waitFor(thunk(), attempt.controller.signal); }
      catch { gate(); throw new ViewError('FETCH_FAILED'); }
      gate(); return result;
    }
    async function readBranch(url, limit, slot) {
      // Construct promise work only after transport admits this branch.
      const response = await transport(() => Promise.resolve().then(() => {
        gate(); return fetchImpl(url, { method: 'GET', headers: { Accept: 'application/json' }, cache: 'no-store', credentials: 'same-origin', redirect: 'error', signal: attempt.controller.signal });
      }).then(response => {
        slot.body = response?.body;
        if (!active()) { cancelSlot(slot); throw STALE; }
        gate(); return response;
      }));
      gate();
      need(response?.status === 200, 'FETCH_FAILED');
      need(response.headers?.get('Content-Type')?.split(';', 1)[0].trim().toLowerCase() === 'application/json');
      need(slot.body && typeof slot.body.getReader === 'function'); slot.reader = slot.body.getReader();
      need(slot.reader && typeof slot.reader.read === 'function'); const chunks = []; let total = 0;
      try {
        while (true) {
          const part = await transport(() => slot.reader.read()); gate();
          need(part && typeof part.done === 'boolean'); if (part.done) { slot.completed = true; break; }
          need(ArrayBuffer.isView(part.value) && Object.prototype.toString.call(part.value) === '[object Uint8Array]');
          total += part.value.byteLength; need(total <= limit, 'RESOURCE_LIMIT');
          if (part.value.byteLength) chunks.push(new Uint8Array(part.value));
        }
      } catch (problem) {
        cancelSlot(slot); throw problem;
      } finally {
        try { slot.reader?.releaseLock?.(); } catch { /* a canceled host reader may have released itself */ }
        slot.reader = null;
      }
      const bytes = new Uint8Array(total); let offset = 0;
      for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
      need(!(bytes[0] === 239 && bytes[1] === 187 && bytes[2] === 191)); let value;
      try { value = JSON.parse(new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes)); }
      catch { throw new ViewError('INVALID_SHAPE'); }
      gate(); return value;
    }
    const branches = [readBranch('/release-if-learned/v1/summary', 65536, attempt.slots[0]), readBranch('/release-if/v1/summary', 16384, attempt.slots[1])];
    void Promise.all(branches).then(async ([value, old]) => {
      gate(); const saved = capture(value, old); await verifyCaptured(saved, gate); gate();
      const fragment = readyFragment(value, old); gate(); content.replaceChildren(fragment); gate();
      root.dataset.state = 'ready'; root.setAttribute('aria-busy', 'false'); status.textContent = '已核对两个保存摘要的身份与声明。';
      attempt.settled = true; clearTimeoutImpl(attempt.timer);
    }).catch(fail);
  }
  function onClick(event) {
    const target = event.target?.closest?.('button[data-action="retry"]');
    if (!destroyed && owns() && target && root.contains(target) && !target.disabled) start();
  }
  function owns() { return mounts.get(root) === entry; }
  function teardown() {
    if (destroyed) return; destroyed = true; lifetime.live = false;
    root.removeEventListener('click', onClick); window.removeEventListener('pagehide', hide);
    // Finalize and release this entry before synchronous abort callbacks remount.
    if (owns()) {
      root.dataset.state = 'destroyed'; root.setAttribute('aria-busy', 'false'); mounts.delete(root);
    }
    cancelAttempt(current);
  }
  function hide() { teardown(); }
  function destroy() { lifetime.disposed = true; teardown(); lifetime.onDispose?.(); }
  const handle = Object.freeze({ destroy }), entry = { handle, lifetime }; mounts.set(root, entry);
  root.addEventListener('click', onClick); window.addEventListener('pagehide', hide, { once: true }); start(); return handle;
}
if (typeof document !== 'undefined') {
  const root = document.querySelector('[data-release-if-learned-view]');
  if (root) {
    let owner = null, suspended = false;
    function unregister() {
      window.removeEventListener('pageshow', restore); window.removeEventListener('pagehide', leave, true);
      if (owner) owner.onDispose = null; owner = null; suspended = false;
    }
    function start() { mountReleaseIFLearnedView(root); owner = mounts.get(root).lifetime; owner.onDispose = unregister; }
    function leave(event) { if (!event.persisted) { unregister(); return; } suspended = owner.live && !owner.disposed; }
    function restore(event) {
      if (!event.persisted || !suspended) return;
      if (!root.isConnected) { unregister(); return; }
      suspended = false; owner.onDispose = null; start();
    }
    start(); window.addEventListener('pagehide', leave, true); window.addEventListener('pageshow', restore);
  }
}
