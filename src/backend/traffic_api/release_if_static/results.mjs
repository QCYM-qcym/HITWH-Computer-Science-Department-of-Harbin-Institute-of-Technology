/* Saved-result display only. No model execution, threshold selection or label evaluation. */
const PROFILE = 'c17-release-iforest-view-v1';
const SCOPE = 'SAVED_RESULT_INTERNAL_CONSISTENCY_ONLY';
const VIEWS = ['current13', 'h30_26'];
const ROLES = ['train', 'validation', 'calibration', 'test'];
const CHECKS = { internal_consistency: 'MATCHED', saved_score_q99: 'MATCHED', cross_view_binding: 'MATCHED',
  input_pair_binding: 'NOT_PERFORMED', source_authentication: 'NOT_AUTHENTICATED', model_execution: 'NOT_AUTHENTICATED' };
const mounts = new WeakMap();
class ViewError extends Error { constructor(code) { super(code); this.code = code; } }
function need(value) { if (!value) throw new ViewError('INVALID_SHAPE'); }
function keys(value, names) {
  need(value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name)));
}
function integer(value, min = 0, max = 10000) { need(Number.isSafeInteger(value) && value >= min && value <= max); }
function finite(value) { need(typeof value === 'number' && Number.isFinite(value)); }
function sha(value) { need(typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)); }
function identity(value, profile) {
  keys(value, ['profile_id', 'context_sha256', 'manifest_sha256', 'manifest_byte_count']);
  need(value.profile_id === profile); sha(value.context_sha256); sha(value.manifest_sha256);
  integer(value.manifest_byte_count, 1, 65536);
}
function segmentID(value) {
  need(typeof value === 'string' && value.length >= 1 && value.length <= 256);
  const points = Array.from(value); need(points.length <= 128);
  need(points.every(point => { const c = point.codePointAt(0); return c >= 32 && c !== 127 && (c < 0xd800 || c > 0xdfff); }));
}
// UTC arithmetic is used only to count source-clock minutes; displayed strings stay unchanged.
function clock(value) {
  need(typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00$/.test(value) && Number(value.slice(0, 4)) >= 1);
  const number = Date.parse(value + 'Z');
  need(Number.isFinite(number) && new Date(number).toISOString().slice(0, 19) === value);
  return number;
}
function envelope(value) {
  need(value.version === 1 && value.profile_id === PROFILE && value.scope === SCOPE); sha(value.snapshot_sha256);
}
export function validateSummary(value) {
  keys(value, ['version', 'profile_id', 'scope', 'snapshot_sha256', 'source', 'input_references', 'result_references', 'axis', 'views', 'checks']);
  envelope(value);
  const source = value.source;
  keys(source, ['schema_id', 'authentication', 'time_basis', 'policy_status', 'audit_fit_policy']);
  need(source.schema_id === 'c17-release-91-v1' && source.authentication === 'NOT_AUTHENTICATED'
    && source.time_basis === 'SOURCE_WALL_CLOCK_COMPLETION_PROXY' && source.policy_status === 'AUDIT_ONLY'
    && ['P_U', 'P_B', 'P_A'].includes(source.audit_fit_policy));
  keys(value.input_references, ['raw', 'prepared', 'configuration_sha256']);
  identity(value.input_references.raw, 'c17-release-minute-package-v1');
  identity(value.input_references.prepared, 'c17-release-prepared-input-package-v1');
  sha(value.input_references.configuration_sha256);
  keys(value.result_references, VIEWS);
  for (const view of VIEWS) identity(value.result_references[view], 'c17-release-iforest-result-package-v1');
  keys(value.checks, Object.keys(CHECKS));
  for (const [key, expected] of Object.entries(CHECKS)) need(value.checks[key] === expected);
  const axis = value.axis;
  keys(axis, ['minute_count', 'scored_count', 'unscored_count', 'page_size', 'page_count', 'segments']);
  integer(axis.minute_count, 1); integer(axis.scored_count); integer(axis.unscored_count);
  need(axis.scored_count + axis.unscored_count === axis.minute_count && axis.page_size === 100
    && axis.page_count === Math.ceil(axis.minute_count / 100));
  need(Array.isArray(axis.segments) && axis.segments.length >= 1 && axis.segments.length <= 7);
  const ids = new Set();
  const roleScored = { train: 0, validation: 0, calibration: 0, test: 0 };
  let total = 0, scored = 0, fitCapacity = 0, previousEnd = -Infinity, previousRole = -1;
  for (const [ordinal, segment] of axis.segments.entries()) {
    keys(segment, ['ordinal', 'id', 'role', 'start', 'end', 'minute_count', 'scored_count']);
    segmentID(segment.id); need(!ids.has(segment.id)); ids.add(segment.id);
    const role = ROLES.indexOf(segment.role), start = clock(segment.start), end = clock(segment.end);
    need(segment.ordinal === ordinal && role >= previousRole && role >= 0 && start >= previousEnd && end > start);
    integer(segment.minute_count, 1); integer(segment.scored_count);
    need((end - start) / 60000 === segment.minute_count && segment.scored_count <= Math.max(0, segment.minute_count - 30));
    total += segment.minute_count; scored += segment.scored_count;
    if (segment.role === 'train') fitCapacity += Math.max(0, segment.minute_count - 30);
    roleScored[segment.role] += segment.scored_count;
    previousEnd = end; previousRole = role;
  }
  need(total === axis.minute_count && scored === axis.scored_count);
  keys(value.views, VIEWS);
  for (const view of VIEWS) {
    const v = value.views[view];
    keys(v, ['configuration', 'threshold', 'training_count', 'calibration_count', 'preprocessing_fit_count', 'equal_threshold_count', 'above_threshold_count']);
    finite(v.threshold);
    for (const field of ['training_count', 'calibration_count', 'preprocessing_fit_count']) integer(v[field], 1);
    integer(v.equal_threshold_count); integer(v.above_threshold_count);
    need(v.training_count <= roleScored.train && v.calibration_count <= roleScored.calibration
      && v.preprocessing_fit_count >= v.training_count && v.preprocessing_fit_count <= fitCapacity
      && v.equal_threshold_count + v.above_threshold_count <= v.calibration_count);
    const c = v.configuration;
    keys(c, ['input_width', 'n_estimators', 'max_samples', 'max_features', 'bootstrap', 'contamination', 'random_state', 'n_jobs']);
    need(c.input_width === (view === 'current13' ? 13 : 26) && c.n_estimators === 16
      && c.max_samples === Math.min(32, v.training_count) && c.max_features === 1 && c.bootstrap === false
      && c.contamination === 'auto' && c.random_state === 42 && c.n_jobs === 1);
  }
  for (const field of ['training_count', 'calibration_count', 'preprocessing_fit_count']) {
    need(value.views.current13[field] === value.views.h30_26[field]);
  }
  return value;
}
async function verifiedSummary(value) {
  validateSummary(value);
  // Only these two validated ASCII identities and the profile enter the canonical envelope.
  const envelope = { ...value.result_references, profile_id: PROFILE };
  const sortedFields = ['context_sha256', 'current13', 'h30_26', 'manifest_byte_count', 'manifest_sha256', 'profile_id'];
  const bytes = new TextEncoder().encode(JSON.stringify(envelope, sortedFields) + '\n');
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  const hex = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
  need(hex === value.snapshot_sha256);
  return value;
}
export function validateSeries(value, summary, page) {
  keys(value, ['version', 'profile_id', 'scope', 'snapshot_sha256', 'page', 'page_size', 'total', 'returned', 'items']);
  envelope(value);
  integer(page, 0, summary.axis.page_count - 1);
  const first = page * 100, returned = Math.min(100, summary.axis.minute_count - first);
  need(value.snapshot_sha256 === summary.snapshot_sha256 && value.page === page && value.page_size === 100
    && value.total === summary.axis.minute_count && value.returned === returned && Array.isArray(value.items) && value.items.length === returned);
  let segmentOffset = 0;
  const segments = summary.axis.segments.map(segment => {
    const result = { segment, offset: segmentOffset, end: segmentOffset + segment.minute_count };
    segmentOffset = result.end; return result;
  });
  let previous = null, pageScored = 0;
  const counts = new Map(segments.map(({ segment }) => [segment.id, { seen: 0, scored: 0, eligibleSeen: 0 }]));
  for (const [local, item] of value.items.entries()) {
    keys(item, ['index', 'timestamp', 'segment_id', 'role', 'break_before', 'scored', 'current13', 'h30_26', 'reason']);
    const index = first + local, expected = segments.find(segment => index >= segment.offset && index < segment.end);
    need(item.index === index && typeof item.scored === 'boolean' && typeof item.break_before === 'boolean' && expected);
    const { segment, offset } = expected;
    need(item.segment_id === segment.id && item.role === segment.role && clock(item.timestamp) === clock(segment.start) + (index - offset) * 60000);
    if (item.scored) need(index - offset >= 30);
    const count = counts.get(segment.id);
    // A scored, nonboundary page start also determines the preceding off-page mask bit.
    if (!previous && item.scored && index > offset) {
      if (!item.break_before) need(index - offset > 30);
      count.seen++; if (index - offset > 30) count.eligibleSeen++;
      if (!item.break_before) count.scored++;
    }
    const boundary = index === 0 || index === offset || !item.scored;
    if (previous) need(item.break_before === (boundary || !previous.scored || previous.segment_id !== item.segment_id
      || clock(item.timestamp) - clock(previous.timestamp) !== 60000));
    else if (boundary) need(item.break_before === true);
    need(item.reason === (item.scored ? null : 'NOT_SCORED_CAUSE_NOT_SAVED'));
    for (const view of VIEWS) {
      const result = item[view]; keys(result, ['score', 'prediction']);
      if (item.scored) {
        finite(result.score); need(typeof result.prediction === 'boolean');
        need(result.prediction === (result.score > summary.views[view].threshold));
      } else need(result.score === null && result.prediction === null);
    }
    count.seen++; if (index - offset >= 30) count.eligibleSeen++;
    if (item.scored) { count.scored++; pageScored++; }
    previous = item;
  }
  need(pageScored <= summary.axis.scored_count && returned - pageScored <= summary.axis.unscored_count);
  for (const { segment } of segments) {
    const count = counts.get(segment.id);
    need(count.scored <= segment.scored_count && count.seen - count.scored <= segment.minute_count - segment.scored_count);
    need(segment.scored_count - count.scored <= Math.max(0, segment.minute_count - 30) - count.eligibleSeen);
    if (count.seen === segment.minute_count) need(count.scored === segment.scored_count);
  }
  return value;
}

export function chartGeometry(items, view, threshold) {
  const scores = items.filter(item => item.scored).map(item => item[view].score);
  const values = [threshold, ...scores], scale = Math.max(1, ...values.map(value => Math.abs(value)));
  const low = Math.min(...values.map(value => value / scale)), high = Math.max(...values.map(value => value / scale));
  const y = value => high === low ? 122 : 214 - ((value / scale - low) / (high - low)) * 184;
  const points = [], runs = []; let run = null, previous = null;
  for (const [local, item] of items.entries()) {
    if (!item.scored) { run = null; previous = item; continue; }
    const point = { x: items.length === 1 ? 328 : 48 + local * 560 / (items.length - 1), y: y(item[view].score),
      index: item.index, score: item[view].score, alarm: item[view].prediction, timestamp: item.timestamp };
    if (!run || item.break_before || !previous?.scored || previous.segment_id !== item.segment_id
      || clock(item.timestamp) - clock(previous.timestamp) !== 60000) { run = []; runs.push(run); }
    run.push(point); points.push(point); previous = item;
  }
  return { points, runs, thresholdY: y(threshold), minimum: Math.min(...values), maximum: Math.max(...values) };
}
function node(tag, text, className) {
  const value = document.createElement(tag); if (text !== undefined) value.textContent = String(text);
  if (className) value.className = className; return value;
}
function svgNode(tag, attributes = {}, text) {
  const value = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [name, item] of Object.entries(attributes)) value.setAttribute(name, String(item));
  if (text !== undefined) value.textContent = String(text); return value;
}
function fact(list, label, text, metric) {
  const value = node('dd', text); if (metric) value.dataset.metric = metric;
  list.append(node('dt', label), value);
}
function button(label, action) { const b = node('button', label); b.type = 'button'; b.dataset.action = action; return b; }
function renderSummary(content, s) {
  const cards = node('div', undefined, 'cards');
  for (const view of VIEWS) {
    const v = s.views[view], card = node('section', undefined, 'panel'); card.dataset.viewCard = view;
    card.append(node('h2', view === 'current13' ? 'current13 · 当前 13 维' : 'H30_26 · 历史 26 维'));
    const list = node('dl', undefined, 'facts');
    for (const [key, label] of [['threshold', '保存的 Q99 阈值'], ['preprocessing_fit_count', '预处理拟合分钟'],
      ['training_count', '模型训练分钟'], ['calibration_count', '独立校准分钟'],
      ['equal_threshold_count', '校准分钟中等于阈值'], ['above_threshold_count', '校准分钟中严格超过阈值']]) fact(list, label, v[key], key);
    card.append(list); cards.append(card);
  }
  const scope = node('section', undefined, 'panel'); scope.append(node('h2', '保存范围与身份'));
  scope.append(node('p', '这些人口覆盖全轴，翻页不会改变。role=train 仅表示源分区，不等于实际模型训练行。校准计数不是全轴报警数。'));
  scope.append(node('p', '仅检查保存内容内部一致性；来源与模型执行未认证。源钟面非认证 UTC，保存报警不是标签。', 'notice'));
  const facts = node('dl', undefined, 'facts');
  fact(facts, '展示范围', s.scope); fact(facts, '快照 SHA256', s.snapshot_sha256);
  fact(facts, '准备配置 SHA256', s.input_references.configuration_sha256);
  for (const [key, value] of Object.entries(s.source)) fact(facts, key, value);
  fact(facts, '全轴分钟 / 已评分 / 未评分', `${s.axis.minute_count} / ${s.axis.scored_count} / ${s.axis.unscored_count}`);
  scope.append(facts);
  const references = node('details'); references.append(node('summary', '查看保存的完整包身份、配置与检查'));
  for (const [label, value] of [['原始分钟包', s.input_references.raw], ['预处理输入包', s.input_references.prepared],
    ['current13 结果包', s.result_references.current13], ['H30_26 结果包', s.result_references.h30_26]]) {
    references.append(node('h3', label)); const list = node('dl', undefined, 'facts');
    for (const [name, text] of Object.entries(value)) fact(list, name, text); references.append(list);
  }
  for (const view of VIEWS) {
    references.append(node('h3', `${view} 保存配置`)); const list = node('dl', undefined, 'facts');
    for (const [name, text] of Object.entries(s.views[view].configuration)) fact(list, name, text); references.append(list);
  }
  const checks = node('dl', undefined, 'facts');
  for (const [name, text] of Object.entries(s.checks)) fact(checks, name, text); references.append(checks);
  scope.append(references); content.replaceChildren(cards, scope);
}
function chart(items, view, threshold) {
  const geometry = chartGeometry(items, view, threshold), section = node('section', undefined, 'panel chart-panel');
  const title = view === 'current13' ? 'current13' : 'H30_26';
  section.append(node('h2', `${title} · 保存分数`), node('p', `独立纵轴 · 保存 Q99 = ${threshold}。圆点为未报警，菱形为报警；未评分处断线。`, 'muted'));
  const svg = svgNode('svg', { viewBox: '0 0 640 260', role: 'img', 'aria-label': `${title} 本页保存分数与 Q99，详细源分钟和报警见下表` });
  svg.append(svgNode('title', {}, `${title} 保存分数；本页源分钟顺序`));
  svg.append(svgNode('line', { x1: 48, y1: 30, x2: 48, y2: 214, class: 'axis' }),
    svgNode('line', { x1: 48, y1: 214, x2: 608, y2: 214, class: 'axis' }),
    svgNode('line', { x1: 48, y1: geometry.thresholdY, x2: 608, y2: geometry.thresholdY, class: 'threshold' }));
  svg.append(svgNode('text', { x: 48, y: 18 }, `范围 ${geometry.minimum} … ${geometry.maximum}`),
    svgNode('text', { x: 328, y: 250, 'text-anchor': 'middle' }, '本页源分钟顺序'),
    svgNode('text', { x: 608, y: Math.max(15, geometry.thresholdY - 6), 'text-anchor': 'end', class: 'threshold-label' }, '保存 Q99'));
  for (const run of geometry.runs) if (run.length > 1) svg.append(svgNode('polyline', { points: run.map(p => `${p.x},${p.y}`).join(' '), class: 'score-line' }));
  for (const p of geometry.points) {
    const mark = p.alarm ? svgNode('path', { d: `M${p.x},${p.y - 5}l5,5l-5,5l-5,-5Z`, class: 'alarm' })
      : svgNode('circle', { cx: p.x, cy: p.y, r: 3.5, class: 'score-dot' });
    mark.append(svgNode('title', {}, `索引 ${p.index} · ${p.timestamp} · ${p.score} · ${p.alarm ? '报警' : '未报警'}`)); svg.append(mark);
  }
  section.append(svg); if (!geometry.points.length) section.append(node('p', '本页全部未评分，包内未保存具体原因。', 'notice'));
  return section;
}
function renderPage(content, value, summary) {
  const charts = node('div', undefined, 'charts');
  for (const view of VIEWS) charts.append(chart(value.items, view, summary.views[view].threshold));
  const section = node('section', undefined, 'panel'); section.append(node('h2', '源分钟明细'));
  const region = node('div', undefined, 'table-region'); region.tabIndex = 0; region.setAttribute('role', 'region');
  region.setAttribute('aria-label', '保存的源分钟与两个视图，可键盘或触屏横向滚动');
  const table = node('table'); table.append(node('caption', '保存的分数、报警与未评分分钟（全轴索引从 0 开始）'));
  const head = node('thead'), header = node('tr');
  for (const label of ['索引', '源钟面分钟', '分区', 'role', '全局断点', 'current13 分数', 'current13 报警', 'H30_26 分数', 'H30_26 报警', '说明']) {
    const th = node('th', label); th.scope = 'col'; header.append(th);
  }
  head.append(header); table.append(head); const body = node('tbody');
  for (const item of value.items) {
    const row = node('tr'); row.dataset.index = item.index;
    const heading = node('th', item.index); heading.scope = 'row'; row.append(heading);
    for (const text of [item.timestamp, item.segment_id, item.role, item.break_before ? '断点' : '连续']) row.append(node('td', text));
    for (const view of VIEWS) {
      row.append(node('td', item.scored ? item[view].score : '未评分'),
        node('td', item.scored ? (item[view].prediction ? '报警' : '未报警') : '未评分', item[view].prediction === true ? 'alarm-text' : ''));
    }
    row.append(node('td', item.scored ? '保存结果；报警不是标签' : '未评分，包内未保存具体原因'));
    body.append(row);
  }
  table.append(body); region.append(table); section.append(region); content.replaceChildren(charts, section);
}
function waitFor(promise, signal) {
  return new Promise((resolve, reject) => {
    let finished = false;
    const finish = (handler, value) => { if (finished) return; finished = true; signal.removeEventListener('abort', abort); handler(value); };
    const abort = () => finish(reject, new ViewError('CANCELLED'));
    signal.addEventListener('abort', abort, { once: true }); if (signal.aborted) abort();
    Promise.resolve(promise).then(value => finish(resolve, value), error => finish(reject, error));
  });
}

export function mountReleaseIFResultView(root, { fetchImpl = globalThis.fetch.bind(globalThis),
  now = () => performance.now(), setTimeoutImpl = globalThis.setTimeout.bind(globalThis),
  clearTimeoutImpl = globalThis.clearTimeout.bind(globalThis) } = {}) {
  if (mounts.has(root)) return mounts.get(root).handle;
  const header = node('header', undefined, 'page-heading');
  header.append(node('p', 'RELEASE · 保存结果只读展示', 'eyebrow'), node('h1', 'IF 结果包检查'),
    node('p', '人工工程示例 · 打开页面仅查看保存结果。真实研究 S2 / Data Gate 仍为 BLOCKED；真实 C17 训练、评分、Q99 与正式实验 NOT_RUN。', 'notice'));
  const status = node('p', '', 'status'); status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  const error = node('p', '', 'error'); error.setAttribute('role', 'alert'); error.hidden = true;
  const retry = node('div', undefined, 'retry'), summaries = node('div'), pageContent = node('div');
  const navigation = node('nav', undefined, 'pagination'); navigation.setAttribute('aria-label', '固定每页 100 个源分钟');
  const previous = button('上一页', 'previous'), next = button('下一页', 'next'), pageLabel = node('span');
  navigation.append(previous, pageLabel, next); navigation.hidden = true;
  root.replaceChildren(header, status, error, retry, summaries, navigation, pageContent);
  let destroyed = false, summary = null, requestedPage = 0;
  const lifetime = { live: true, disposed: false };
  const slots = { summary: { generation: 0, request: null }, page: { generation: 0, request: null } };
  function nav() {
    navigation.hidden = !summary; previous.disabled = !summary || requestedPage === 0;
    next.disabled = !summary || requestedPage === summary.axis.page_count - 1;
    pageLabel.textContent = summary ? `第 ${requestedPage + 1} / ${summary.axis.page_count} 页 · 每页 100 分钟` : '';
  }
  function clearError() { error.textContent = ''; error.hidden = true; retry.replaceChildren(); }
  function failure(problem, kind) {
    const code = problem instanceof ViewError ? problem.code : 'FETCH_FAILED';
    error.textContent = code === 'TIMEOUT' ? '读取超时（10秒）。'
      : code === 'RESOURCE_LIMIT' ? '响应超出读取上限。' : code === 'INVALID_SHAPE' ? '响应格式不匹配。' : '读取失败。';
    pageContent.setAttribute('aria-busy', 'false');
    error.hidden = false; root.dataset.state = 'error'; status.textContent = kind === 'summary' ? '未能读取保存摘要。' : '未能读取本页，已清空旧图表；全轴摘要保留。';
    retry.replaceChildren(button(kind === 'summary' ? '重试加载' : '重试本页', kind === 'summary' ? 'retry-summary' : 'retry-page'));
  }
  function stop(kind) {
    const slot = slots[kind]; slot.generation++; slot.request?.cancel(); slot.request = null;
  }
  function request(kind, url, limit, validate, success) {
    stop(kind); const slot = slots[kind], generation = slot.generation;
    const controller = new AbortController(), deadline = now() + 10000;
    let reader = null, body = null, timer, settled = false, cancelledTarget = null;
    const active = () => !destroyed && slot.generation === generation && !settled;
    function cancelBody() {
      const target = reader ?? body; if (!target || target === cancelledTarget) return;
      cancelledTarget = target;
      try { if (typeof target.cancel === 'function') Promise.resolve(target.cancel()).catch(() => {}); } catch { /* best effort */ }
    }
    function cancel() { settled = true; controller.abort(); cancelBody(); clearTimeoutImpl(timer); }
    function fail(problem) {
      if (!active()) return;
      cancel(); failure(problem, kind);
    }
    function requireActive() {
      if (!active()) throw new ViewError('CANCELLED');
      if (now() >= deadline) throw new ViewError('TIMEOUT');
    }
    slot.request = { cancel };
    timer = setTimeoutImpl(() => fail(new ViewError('TIMEOUT')), 10000);
    void (async () => {
      try {
        const fetching = Promise.resolve(fetchImpl(url, { method: 'GET', headers: { Accept: 'application/json' },
          cache: 'no-store', credentials: 'same-origin', redirect: 'error', signal: controller.signal })).then(response => {
          body = response?.body;
          if (controller.signal.aborted) cancelBody();
          return response;
        });
        const response = await waitFor(fetching, controller.signal); requireActive();
        if (response?.status !== 200) throw new ViewError('FETCH_FAILED');
        const media = response.headers?.get('Content-Type')?.split(';', 1)[0].trim().toLowerCase();
        need(media === 'application/json' && body && typeof body.getReader === 'function');
        reader = body.getReader(); need(reader && typeof reader.read === 'function');
        const chunks = []; let total = 0;
        try {
          while (true) {
            requireActive(); const part = await waitFor(reader.read(), controller.signal); requireActive();
            need(part && typeof part.done === 'boolean'); if (part.done) break;
            need(ArrayBuffer.isView(part.value) && Object.prototype.toString.call(part.value) === '[object Uint8Array]');
            total += part.value.byteLength; if (total > limit) throw new ViewError('RESOURCE_LIMIT');
            if (part.value.byteLength) chunks.push(new Uint8Array(part.value));
          }
        } catch (problem) { cancelBody(); throw problem; }
        finally {
          try { if (typeof reader?.releaseLock === 'function') reader.releaseLock(); } catch { /* cancelled host readers may already be released */ }
          reader = null;
        }
        const payload = new Uint8Array(total); let offset = 0;
        for (const chunk of chunks) { payload.set(chunk, offset); offset += chunk.byteLength; }
        let value;
        try { value = JSON.parse(new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(payload)); }
        catch { throw new ViewError('INVALID_SHAPE'); }
        requireActive(); const parsed = await waitFor(validate(value), controller.signal); requireActive();
        settled = true; clearTimeoutImpl(timer); success(parsed);
      } catch (problem) { fail(problem); }
    })();
  }
  function loadPage(page) {
    if (destroyed || !summary || !Number.isInteger(page) || page < 0 || page >= summary.axis.page_count) return;
    requestedPage = page; pageContent.replaceChildren(); clearError(); nav(); root.dataset.state = 'loading-page';
    pageContent.setAttribute('aria-busy', 'true'); status.textContent = `正在读取第 ${page + 1} 页…`;
    const bound = summary;
    request('page', `/release-if/v1/series?page=${page}`, 131072, value => validateSeries(value, bound, page), value => {
      renderPage(pageContent, value, bound); pageContent.setAttribute('aria-busy', 'false');
      status.textContent = `已读取第 ${page + 1} / ${bound.axis.page_count} 页，${value.returned} 个源分钟。`;
      root.dataset.state = 'ready';
    });
  }
  function loadSummary() {
    if (destroyed) return;
    stop('page'); summary = null; summaries.replaceChildren(); pageContent.replaceChildren(); clearError(); nav();
    status.textContent = '正在读取保存结果摘要…'; root.dataset.state = 'loading-summary';
    request('summary', '/release-if/v1/summary', 16384, verifiedSummary, value => {
      summary = value; renderSummary(summaries, value); loadPage(0);
    });
  }
  function onClick(event) {
    if (destroyed) return;
    const target = event.target?.closest?.('button[data-action]'); if (!target || !root.contains(target) || target.disabled) return;
    const action = target.dataset.action;
    if (action === 'previous') loadPage(requestedPage - 1);
    else if (action === 'next') loadPage(requestedPage + 1);
    else if (action === 'retry-page') loadPage(requestedPage);
    else if (action === 'retry-summary') loadSummary();
  }
  function teardown() {
    if (destroyed) return; destroyed = true; lifetime.live = false; stop('summary'); stop('page');
    root.removeEventListener('click', onClick); window.removeEventListener('pagehide', hide); mounts.delete(root);
  }
  function hide() { teardown(); }
  function destroy() { lifetime.disposed = true; teardown(); lifetime.onDispose?.(); }
  const handle = Object.freeze({ destroy }); mounts.set(root, { handle, lifetime });
  root.addEventListener('click', onClick); window.addEventListener('pagehide', hide, { once: true });
  loadSummary(); return handle;
}
if (typeof document !== 'undefined') {
  const root = document.querySelector('[data-release-if-result-view]');
  if (root) {
    let owner = null, suspended = false;
    function unregister() {
      window.removeEventListener('pageshow', restore);
      window.removeEventListener('pagehide', leave, true);
      if (owner) owner.onDispose = null;
      owner = null;
      suspended = false;
    }
    function start() {
      mountReleaseIFResultView(root);
      owner = mounts.get(root).lifetime;
      owner.onDispose = unregister;
    }
    function restore(event) {
      if (!event.persisted || !suspended) return;
      if (!root.isConnected) { unregister(); return; }
      suspended = false;
      owner.onDispose = null; // A handle from before restoration no longer owns the window listeners.
      start();
    }
    function leave(event) {
      if (!event.persisted) { unregister(); return; }
      suspended = owner.live && !owner.disposed;
    }
    // Capture the live lifetime before the viewer's own pagehide teardown runs.
    start();
    window.addEventListener('pageshow', restore); window.addEventListener('pagehide', leave, true);
  }
}
