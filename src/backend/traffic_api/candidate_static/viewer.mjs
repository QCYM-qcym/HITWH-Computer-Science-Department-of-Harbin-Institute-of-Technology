/* Candidate-only saved-result consumer. No model, UTC conversion or metric calculation. */
const BASE = '/candidate/v1/runs';
const POLICIES = ['P_U', 'P_B', 'P_A'];
const PROOFS = ['VERIFIED', 'NOT_PROVIDED'];
const REASONS = [null, 'warmup', 'gap', 'boundary', 'invalid_input', 'nonfinite_history'];
const MINUTE = /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:00\.000000$/;
const finite = value => typeof value === 'number' && Number.isFinite(value);
const integer = value => Number.isSafeInteger(value) && value >= 0;
const canonical = value => value === null ? null : value.slice(0, 16) + ':00.000000';
const display = value => value === null ? '未提供' : Object.is(value, -0) ? '-0' : String(value);
function requireValue(value) { if (!value) throw new Error('INVALID_RESPONSE'); }
function shared(value, id) {
  requireValue(value?.schema_version === 1 && value.evidence_kind === 'SYNTHETIC_ONLY'
    && value.policy_status === 'AUDIT_ONLY' && value.time_basis === 'synthetic_source_clock'
    && value.run_id === id && POLICIES.includes(value.selected_policy));
}
function proof(value) {
  requireValue(value && PROOFS.includes(value.run) && PROOFS.includes(value.inputs)
    && value.combined === (value.run === 'VERIFIED' && value.inputs === 'VERIFIED' ? 'VERIFIED' : 'NOT_PROVIDED'));
}
function checkCatalog(value) {
  requireValue(value?.schema_version === 1 && value.evidence_kind === 'SYNTHETIC_ONLY' && value.policy_status === 'AUDIT_ONLY'
    && value.scope === 'SYNTHETIC_SAVED_RUN_INSPECTION_ONLY' && Array.isArray(value.items) && value.items.length >= 1 && value.items.length <= 4);
  const seen = new Set();
  for (const item of value.items) {
    requireValue(typeof item.run_id === 'string' && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(item.run_id) && !seen.has(item.run_id)
      && typeof item.model_profile_id === 'string' && POLICIES.includes(item.selected_policy)
      && integer(item.minute_count) && integer(item.score_valid_count) && item.score_valid_count <= item.minute_count
      && (['iforest', 'current_ae'].includes(item.method) ? item.history_window === null
        : item.method === 'history_ae' && [15, 30].includes(item.history_window)));
    proof(item.source_replay); seen.add(item.run_id);
  }
  return value;
}
function checkPoint(point) {
  requireValue(point && typeof point.timestamp === 'string' && MINUTE.test(point.timestamp)
    && typeof point.segment_id === 'string' && ['train', 'validation', 'calibration', 'test'].includes(point.partition)
    && typeof point.valid === 'boolean' && finite(point.threshold)
    && (point.valid ? finite(point.score) && typeof point.alarm === 'boolean' : point.score === null && point.alarm === null));
}
function checkSeries(value, id, query) {
  shared(value, id);
  requireValue(PROOFS.includes(value.source_replay) && value.page === query.page && value.page_size === query.page_size
    && integer(value.total) && integer(value.returned) && value.total <= 10000
    && Array.isArray(value.items) && value.items.length === value.returned && value.returned <= query.page_size && value.returned <= value.total
    && value.range?.start === canonical(query.start) && value.range?.end === canonical(query.end));
  let previous = '';
  for (const point of value.items) {
    checkPoint(point);
    requireValue(integer(point.source_index) && point.source_index < 10000 && typeof point.current_input_valid === 'boolean'
      && typeof point.break_before === 'boolean' && point.timestamp > previous
      && REASONS.includes(point.history_invalid_reason?.['15']) && REASONS.includes(point.history_invalid_reason?.['30']));
    previous = point.timestamp;
  }
  const ref = value.evaluation_reference;
  requireValue(ref?.scope === 'FULL_STORED_RUN' && ref.run_id === id && /^[a-f0-9]{64}$/.test(ref.artifact?.sha256)
    && integer(ref.artifact.byte_count) && ref.artifact.byte_count > 0);
  return value;
}
function channel(value, key) {
  requireValue(value && typeof value.valid === 'boolean' && Array.isArray(value[key]) && value[key].length === 13
    && value[key].every(number => value.valid ? finite(number) : number === null));
}
function checkDetail(value, id, timestamp) {
  shared(value, id); proof(value.source_replay); checkPoint(value.point);
  requireValue(value.point.timestamp === timestamp && Array.isArray(value.feature_names) && value.feature_names.length === 13
    && value.feature_names.every(name => typeof name === 'string') && new Set(value.feature_names).size === 13);
  channel(value.inputs?.raw, 'values'); channel(value.inputs?.prepared, 'values');
  for (const h of ['15', '30']) {
    const history = value.histories?.[h]; channel(history, 'residual');
    requireValue(REASONS.includes(history.invalid_reason) && (history.invalid_reason === null) === history.valid);
  }
  requireValue(typeof value.labels?.source_attack_label_present === 'boolean'
    && POLICIES.every(p => ['normal', 'attack', 'unknown'].includes(value.labels.policies?.[p])));
  for (const name of ['current', 'history_deviation']) {
    const item = value.reconstruction?.[name];
    requireValue(item && ['APPLICABLE', 'NOT_APPLICABLE'].includes(item.status)
      && (item.status === 'NOT_APPLICABLE' ? item.value === null : item.value === null || finite(item.value) && item.value >= 0));
  }
  requireValue(value.reconstruction.per_feature?.status === 'NOT_STORED' && value.reconstruction.per_feature.values === null);
  return value;
}

export function chartGeometry(items) {
  if (!items.length) return {scorePaths: [], thresholdPaths: [], points: [], thresholdPoints: [], low: null, high: null};
  const values = items.flatMap(row => [row.score, row.threshold]).filter(finite);
  if (!values.length) return {scorePaths: [], thresholdPaths: [], points: [], thresholdPoints: [], low: null, high: null};
  const scale = Math.max(1, ...values.map(Math.abs));
  let low = Math.min(...values.map(v => v / scale)), high = Math.max(...values.map(v => v / scale));
  if (low === high) { low -= .05; high += .05; }
  const x = i => items.length === 1 ? 450 : 40 + i * 820 / (items.length - 1);
  const y = value => 220 - (value / scale - low) * 190 / (high - low);
  function paths(key) {
    const result = []; let path = '';
    items.forEach((row, i) => {
      if (row.break_before || !finite(row[key])) { if (path) result.push(path); path = ''; }
      if (finite(row[key])) path += `${path ? ' L' : 'M'}${x(i)} ${y(row[key])}`;
    });
    if (path) result.push(path);
    return result;
  }
  return {scorePaths: paths('score'), thresholdPaths: paths('threshold'),
    points: items.flatMap((row, i) => finite(row.score) ? [{x: x(i), y: y(row.score), index: i}] : []),
    thresholdPoints: items.flatMap((row, i) => finite(row.threshold) ? [{x: x(i), y: y(row.threshold), index: i}] : []),
    low: Math.min(...values), high: Math.max(...values)};
}

const LAYOUT = `
  <p class="eyebrow">本地保存结果 · 独立查看</p><h1>候选合成结果</h1>
  <div class="notice"><strong>SYNTHETIC_ONLY · AUDIT_ONLY</strong><p>仅用于人工结果的工程核查，不代表主数据已采用、研究效果或 Data Gate 通过。</p>
  <p>时间为 synthetic_source_clock 源钟面坐标，不作 UTC 或本地时区转换。</p></div>
  <section class="panel"><h2>选择已保存运行</h2><div class="controls"><label>运行 ID<select id="run-select" disabled><option value="">请选择运行</option></select></label>
  <button id="reload-catalog" class="secondary">重新读取目录</button></div><p id="catalog-status" class="status" role="status"></p><p id="catalog-error" class="error" role="alert"></p>
  <p id="run-context" class="mono"></p><p id="source-proof" class="muted"></p></section>
  <section class="panel"><h2>当前页分钟记录</h2><form id="range-form" class="controls">
  <label>起点（包含）<input id="range-start" placeholder="2026-01-01T00:00"></label><label>终点（不包含）<input id="range-end" placeholder="2026-01-01T01:00"></label>
  <label>每页记录<select id="page-size"><option value="1">1</option><option value="17">17</option><option value="100" selected>100</option><option value="1000">1000</option></select></label>
  <button id="apply-range" disabled>应用范围</button></form><p class="muted">源钟面整分钟；草稿只有点击应用后生效。曲线按当前页记录顺序绘制，缺口断开，不表示等间距的真实时间。</p>
  <p id="series-status" class="status" role="status"></p><p id="series-error" class="error" role="alert"></p><p id="series-summary" class="mono"></p>
  <p id="saved-threshold"></p><svg id="score-chart" class="chart" viewBox="0 0 900 250" role="img" aria-label="当前页异常分数与保存阈值，空值及原始断点不连线"></svg>
  <p id="chart-scale" class="muted"></p><div class="table-scroll"><table><thead><tr><th>源分钟</th><th>分数</th><th>保存阈值</th><th>状态</th><th>H15 / H30</th><th>原始断点</th><th>详情</th></tr></thead><tbody id="minute-rows"></tbody></table></div>
  <div class="pagination"><button id="previous-page" class="secondary" disabled>上一页</button><span id="page-context"></span><button id="next-page" class="secondary" disabled>下一页</button></div>
  <p class="muted">范围与分页只改变显示行；不重新计算阈值或评价指标。</p><p id="evaluation-reference" class="mono muted"></p></section>
  <section class="panel"><h2>分钟详情</h2><p id="detail-status" class="status" role="status"></p><p id="detail-error" class="error" role="alert"></p><div id="minute-detail">选择分钟查看独立通道。</div></section>`;

function element(tag, text, className) {
  const node = document.createElement(tag); if (text !== undefined) node.textContent = text;
  if (className) node.className = className; return node;
}
function message(error) {
  return ({INVALID_RESPONSE: '结果格式不匹配，请重新读取。', INVALID_QUERY: '查询无效，请检查源分钟范围和页码。',
    RUN_NOT_FOUND: '运行未登记，请重新读取目录。', MINUTE_NOT_FOUND: '该源分钟没有保存记录。',
    RESOURCE_LIMIT: '响应超过读取上限。', INTERNAL_ERROR: '服务未能读取结果，请重试。'})[error?.message] ?? '读取失败，请重试。';
}

export function mountViewer(root, {fetcher = globalThis.fetch.bind(globalThis)} = {}) {
  root.innerHTML = LAYOUT; // Fixed local markup only. Every external value uses textContent.
  const ids = new Map([...root.querySelectorAll('[id]')].map(node => [node.id, node]));
  const get = id => ids.get(id), text = (id, value) => { get(id).textContent = value; };
  const versions = {catalog: 0, series: 0, detail: 0}, controllers = {};
  let disposed = false, catalog = [], selected = null, pageData = null;
  let applied = {start: null, end: null, page: 1, page_size: 100};
  function invalidate(kind) { versions[kind]++; controllers[kind]?.abort(); }
  function begin(kind) { invalidate(kind); controllers[kind] = new AbortController(); return {version: versions[kind], controller: controllers[kind]}; }
  const current = (kind, task) => !disposed && versions[kind] === task.version;
  async function read(url, signal) {
    const response = await fetcher(url, {method: 'GET', signal});
    const body = await response.json();
    if (!response.ok) {
      const code = ['INVALID_QUERY','RUN_NOT_FOUND','MINUTE_NOT_FOUND','RESOURCE_LIMIT','INTERNAL_ERROR'].includes(body?.error) ? body.error : 'FETCH_FAILED';
      throw new Error(code);
    }
    return body;
  }
  function clearDetail() { invalidate('detail'); text('minute-detail', '选择分钟查看独立通道。'); text('detail-error', ''); text('detail-status', ''); }
  function clearSeries() {
    invalidate('series'); clearDetail(); pageData = null;
    for (const id of ['series-summary','series-error','series-status','page-context','evaluation-reference','chart-scale']) text(id, '');
    get('minute-rows').replaceChildren(); get('score-chart').replaceChildren();
    text('saved-threshold', '保存阈值：未提供（没有当前页记录）');
    get('previous-page').disabled = true; get('next-page').disabled = true;
  }
  function draw(page) {
    const geometry = chartGeometry(page.items), svg = get('score-chart'); svg.replaceChildren();
    function svgNode(tag, attributes) { const node = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const [key,value] of Object.entries(attributes)) node.setAttribute(key, String(value)); svg.append(node); }
    for (const path of geometry.thresholdPaths) svgNode('path', {d: path, class: 'threshold-line'});
    for (const path of geometry.scorePaths) svgNode('path', {d: path, class: 'score-line'});
    for (const point of geometry.thresholdPoints) svgNode('circle', {cx: point.x, cy: point.y, r: 5, class: 'threshold-point'});
    for (const point of geometry.points) svgNode('circle', {cx: point.x, cy: point.y, r: 4, class: page.items[point.index].alarm ? 'alarm-point' : 'score-point'});
    text('chart-scale', geometry.low === null ? '' : `分数/阈值范围 ${display(geometry.low)} — ${display(geometry.high)} · 绿色为分数，橙色空心点及虚线为保存阈值；不抽样。`);
    const rows = get('minute-rows'); rows.replaceChildren();
    for (const point of page.items) {
      const row = element('tr');
      for (const value of [point.timestamp, display(point.score), display(point.threshold), !point.valid ? '未评分' : point.alarm ? '报警' : '未报警',
        `${point.history_invalid_reason['15'] ?? '可用'} / ${point.history_invalid_reason['30'] ?? '可用'}`, point.break_before ? '是' : '否']) row.append(element('td', value));
      const cell = element('td'), button = element('button', '查看'); button.type = 'button'; button.dataset.timestamp = point.timestamp;
      button.setAttribute('aria-label', `查看 ${point.timestamp} 的详情`); button.addEventListener('click', () => { void loadDetail(point.timestamp); }); cell.append(button); row.append(cell); rows.append(row);
    }
    text('series-summary', `${page.run_id} · 范围 ${page.range.start ?? '不限'} → ${page.range.end ?? '不限'}（终点不包含）`);
    text('page-context', `第 ${page.page} 页 · 当前 ${page.returned} / 范围内 ${page.total} 行（含无效分钟）`);
    text('saved-threshold', page.items.length ? `保存阈值：${display(page.items[0].threshold)}（无效分钟仍保留该参考值）` : '保存阈值：未提供（没有当前页记录）');
    text('series-status', page.items.length ? '' : '当前页没有分钟记录。');
    const reference = page.evaluation_reference;
    text('evaluation-reference', `${reference.scope} · ${reference.run_id} · SHA-256 ${reference.artifact.sha256} · ${reference.artifact.byte_count} bytes。仅引用完整保存评价，未在页面计算指标。`);
    get('previous-page').disabled = page.page <= 1; get('next-page').disabled = page.page * page.page_size >= page.total;
  }
  function drawDetail(value) {
    const panel = get('minute-detail'); panel.replaceChildren();
    panel.append(element('h3', value.point.timestamp, 'detail-heading'), element('p',
      `${value.run_id} · ${value.point.valid ? value.point.alarm ? '报警' : '未报警' : '未评分'} · 分数 ${display(value.point.score)} · 保存阈值 ${display(value.point.threshold)}`));
    panel.append(element('p', `来源核对 ${value.source_replay.combined}；${POLICIES.map(p => `${p}: ${value.labels.policies[p]}`).join(' · ')}；源攻击标签存在: ${value.labels.source_attack_label_present}。这些政策仅作审计对照。`, 'muted'));
    panel.append(element('p', `raw: ${value.inputs.raw.valid ? '可用' : '未提供'} · prepared: ${value.inputs.prepared.valid ? '可用' : '未提供'} · H15: ${value.histories['15'].invalid_reason ?? '可用'} · H30: ${value.histories['30'].invalid_reason ?? '可用'}`));
    const reconstruction = element('p'); reconstruction.id = 'reconstruction';
    reconstruction.textContent = `保存组标量MSE · 当前 ${value.reconstruction.current.status} · ${display(value.reconstruction.current.value)}；历史 ${value.reconstruction.history_deviation.status} · ${display(value.reconstruction.history_deviation.value)}。逐特征重构：NOT_STORED（未保存，不分摊组标量）。`;
    panel.append(reconstruction);
    const scroll = element('div', undefined, 'table-scroll'), table = element('table'), head = element('thead'), header = element('tr');
    for (const title of ['特征（保存顺序）','原始 raw','预处理 prepared','H15 历史偏离','H30 历史偏离']) header.append(element('th', title));
    head.append(header); table.append(head); const body = element('tbody'); body.id = 'feature-rows';
    value.feature_names.forEach((name, i) => { const row = element('tr'); row.append(element('td', name));
      for (const v of [value.inputs.raw.values[i], value.inputs.prepared.values[i], value.histories['15'].residual[i], value.histories['30'].residual[i]]) row.append(element('td', display(v)));
      body.append(row); }); table.append(body); scroll.append(table); panel.append(scroll);
  }
  async function loadSeries(query) {
    clearSeries(); if (!selected) return;
    applied = {...query}; const id = selected.run_id, request = {...applied}, task = begin('series');
    text('series-status', '读取中…'); get('apply-range').disabled = true;
    const params = new URLSearchParams({page: String(request.page), page_size: String(request.page_size)});
    for (const key of ['start','end']) if (request[key] !== null) params.set(key, request[key]);
    try {
      const value = await read(`${BASE}/${encodeURIComponent(id)}/series?${params}`, task.controller.signal);
      if (!current('series', task) || selected?.run_id !== id) return;
      pageData = checkSeries(value, id, request); draw(pageData);
    } catch (error) { if (current('series', task)) { text('series-error', message(error)); text('series-status', ''); } }
    finally { if (current('series', task)) { get('apply-range').disabled = false; if (get('series-status').textContent === '读取中…') text('series-status', ''); } }
  }
  async function loadDetail(timestamp) {
    clearDetail(); if (!selected || !pageData) return;
    const id = selected.run_id, task = begin('detail'); text('detail-status', '读取中…');
    try {
      const params = new URLSearchParams({timestamp});
      const value = await read(`${BASE}/${encodeURIComponent(id)}/detail?${params}`, task.controller.signal);
      if (!current('detail', task) || selected?.run_id !== id) return;
      drawDetail(checkDetail(value, id, timestamp));
    } catch (error) { if (current('detail', task)) text('detail-error', message(error)); }
    finally { if (current('detail', task)) text('detail-status', ''); }
  }
  async function reloadCatalog() {
    clearSeries(); selected = null; catalog = []; get('apply-range').disabled = true; get('run-select').disabled = true;
    get('run-select').replaceChildren(new Option('请选择运行', '')); text('run-context', ''); text('source-proof', '');
    text('catalog-error', ''); text('catalog-status', '读取中…'); const task = begin('catalog');
    try {
      const value = await read(BASE, task.controller.signal);
      if (!current('catalog', task)) return;
      catalog = checkCatalog(value).items;
      for (const item of catalog) get('run-select').append(new Option(`${item.run_id} · ${item.method}${item.history_window === null ? '' : ` H${item.history_window}`}`, item.run_id));
      get('run-select').disabled = false;
    } catch (error) { if (current('catalog', task)) text('catalog-error', message(error)); }
    finally { if (current('catalog', task)) text('catalog-status', ''); }
  }
  get('run-select').addEventListener('change', () => {
    selected = catalog.find(item => item.run_id === get('run-select').value) ?? null; clearSeries();
    text('run-context', selected ? `${selected.run_id} · ${selected.method} · ${selected.selected_policy}（审计政策）` : '');
    text('source-proof', selected ? `来源证明：run ${selected.source_replay.run} / inputs ${selected.source_replay.inputs} / combined ${selected.source_replay.combined}` : '');
    get('range-start').value = ''; get('range-end').value = ''; get('page-size').value = '100';
    get('apply-range').disabled = !selected; if (selected) void loadSeries({start: null, end: null, page: 1, page_size: 100});
  });
  get('range-form').addEventListener('submit', event => { event.preventDefault(); if (selected) void loadSeries({
    start: get('range-start').value || null, end: get('range-end').value || null, page: 1, page_size: Number(get('page-size').value)}); });
  for (const [id, delta] of [['previous-page', -1], ['next-page', 1]]) get(id).addEventListener('click', () => { if (selected && pageData) void loadSeries({...applied, page: applied.page + delta}); });
  get('reload-catalog').addEventListener('click', () => { void reloadCatalog(); });
  void reloadCatalog();
  return {reloadCatalog, dispose() { disposed = true; for (const kind of Object.keys(versions)) invalidate(kind); root.replaceChildren(); }};
}

const root = typeof document === 'undefined' ? null : document.getElementById('candidate-viewer');
if (root) mountViewer(root);
