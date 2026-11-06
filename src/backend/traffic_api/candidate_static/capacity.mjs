/* Capacity-only display consumer. Canonical fixed definitions below match the
 * Python-validated display fixtures; no artifact/model/qualification algorithms. */
const FIXED_CONFIGURATIONS = {"current_ae13":{"activation":"RELU_HIDDEN_LINEAR_OUTPUT","adam_betas":[0.9,0.999],"adam_epsilon":1e-08,"alarm_comparison":"STRICT_GREATER","amsgrad":false,"architecture":[13,8,3,8,13],"batch_strategy":"FULL_BATCH","calibration_scope":"CALIBRATION_NORMAL_COMMON","device":"cpu","epochs":5,"fit_scope":"TRAIN_NORMAL_COMMON","history_window":null,"input_width":13,"learning_rate":0.001,"method":"current_ae","model_profile_id":"c17-i1-g13u-ae-synthetic-v1","optimizer":"Adam","optimizer_cpu_guard":"INSTANCE_LOCAL_HEALTH_CHECK_V1","optimizer_healthcheck_api":"_accelerator_graph_capture_health_check","parameter_count":288,"parameter_status":"ENGINEERING_TOY_ONLY","preprocessing_fit_provenance":"NOT_REESTIMATED","quantile":0.99,"quantile_method":"linear","random_state":42,"score_dtype":"float64","score_rule":"FLOAT64_CHANNEL_MSE_EQUAL_WEIGHT","shuffle":false,"training_dtype":"float32","weight_decay":0.0},"current_ae13_capacity492":{"activation":"RELU_HIDDEN_LINEAR_OUTPUT","adam_betas":[0.9,0.999],"adam_epsilon":1e-08,"alarm_comparison":"STRICT_GREATER","amsgrad":false,"architecture":[13,14,3,14,13],"batch_strategy":"FULL_BATCH","calibration_scope":"CALIBRATION_NORMAL_COMMON","device":"cpu","epochs":5,"fit_scope":"TRAIN_NORMAL_COMMON","history_window":null,"input_width":13,"learning_rate":0.001,"method":"current_ae","model_profile_id":"c17-i1-g13u-ae-current-capacity492-synthetic-v1","optimizer":"Adam","optimizer_cpu_guard":"INSTANCE_LOCAL_HEALTH_CHECK_V1","optimizer_healthcheck_api":"_accelerator_graph_capture_health_check","parameter_count":492,"parameter_status":"ENGINEERING_TOY_ONLY","preprocessing_fit_provenance":"NOT_REESTIMATED","quantile":0.99,"quantile_method":"linear","random_state":42,"score_dtype":"float64","score_rule":"FLOAT64_CHANNEL_MSE_EQUAL_WEIGHT","shuffle":false,"training_dtype":"float32","weight_decay":0.0},"history_ae26_h15":{"activation":"RELU_HIDDEN_LINEAR_OUTPUT","adam_betas":[0.9,0.999],"adam_epsilon":1e-08,"alarm_comparison":"STRICT_GREATER","amsgrad":false,"architecture":[26,8,3,8,26],"batch_strategy":"FULL_BATCH","calibration_scope":"CALIBRATION_NORMAL_COMMON","device":"cpu","epochs":5,"fit_scope":"TRAIN_NORMAL_COMMON","history_window":15,"input_width":26,"learning_rate":0.001,"method":"history_ae","model_profile_id":"c17-i1-g13u-ae-synthetic-v1","optimizer":"Adam","optimizer_cpu_guard":"INSTANCE_LOCAL_HEALTH_CHECK_V1","optimizer_healthcheck_api":"_accelerator_graph_capture_health_check","parameter_count":509,"parameter_status":"ENGINEERING_TOY_ONLY","preprocessing_fit_provenance":"NOT_REESTIMATED","quantile":0.99,"quantile_method":"linear","random_state":42,"score_dtype":"float64","score_rule":"FLOAT64_CHANNEL_MSE_EQUAL_WEIGHT","shuffle":false,"training_dtype":"float32","weight_decay":0.0},"history_ae26_h30":{"activation":"RELU_HIDDEN_LINEAR_OUTPUT","adam_betas":[0.9,0.999],"adam_epsilon":1e-08,"alarm_comparison":"STRICT_GREATER","amsgrad":false,"architecture":[26,8,3,8,26],"batch_strategy":"FULL_BATCH","calibration_scope":"CALIBRATION_NORMAL_COMMON","device":"cpu","epochs":5,"fit_scope":"TRAIN_NORMAL_COMMON","history_window":30,"input_width":26,"learning_rate":0.001,"method":"history_ae","model_profile_id":"c17-i1-g13u-ae-synthetic-v1","optimizer":"Adam","optimizer_cpu_guard":"INSTANCE_LOCAL_HEALTH_CHECK_V1","optimizer_healthcheck_api":"_accelerator_graph_capture_health_check","parameter_count":509,"parameter_status":"ENGINEERING_TOY_ONLY","preprocessing_fit_provenance":"NOT_REESTIMATED","quantile":0.99,"quantile_method":"linear","random_state":42,"score_dtype":"float64","score_rule":"FLOAT64_CHANNEL_MSE_EQUAL_WEIGHT","shuffle":false,"training_dtype":"float32","weight_decay":0.0}};
const FIXED_CONFIGURATION_DIGESTS = {"current_ae13":"3ee1b94e867b968987106d539ea3f3cf5c40c4f8f35d2a0e0a89c5812c9607d1","current_ae13_capacity492":"817e3894b757386785d530e7c4d6882ab2ccdf455544546cf5e4cf4a3241fb5c","history_ae26_h15":"8c54074134fe276b0329b0445f6e518333607dca7eb881b56563d1ada409d1b9","history_ae26_h30":"88a2a59bb35b55413eb865796c1aba845e158bfbbfb8d4d951873dd4e52d3eb1"};
const FIXED_FEATURES = ["completed_source_record_count","fwd_packet_sum","bwd_packet_sum","fwd_source_length_sum","bwd_source_length_sum","tcp_source_record_count","udp_source_record_count","known_other_source_protocol_record_count","unresolved_source_protocol_record_count","duration_max_s","duration_median_s","duration_p95_s","no_backward_packet_source_record_count"];
const FIXED_PROTOCOL = {"alarm_comparison":"STRICT_GREATER","calibration_scope":"CALIBRATION_NORMAL_COMMON","fit_scope":"TRAIN_NORMAL_COMMON","preprocessing_fit_provenance":"NOT_REESTIMATED","quantile":0.99,"quantile_method":"linear"};
const FIXED_CHECKS = {"byte_integrity":"VERIFIED","evaluation":"VERIFIED","library_versions":"DECLARATION_CONSISTENT_ONLY","model_deserialization":"NOT_PERFORMED","model_origin":"NOT_AUTHENTICATED","model_score_replay":"NOT_CHECKED","network_reconstruction":"NOT_PERFORMED","source_replay":"VERIFIED","stored_channel_score_relation":"VERIFIED","stored_score_calibration":"VERIFIED","strict_alarms":"VERIFIED","training_execution":"NOT_CHECKED","training_loss_replay":"NOT_CHECKED","upstream_lineage":"VERIFIED","weights_json_structure":"VERIFIED"};
const FIXED_LIMITATIONS = {"capacity_control":"NOT_COMPARABLE","capacity_control_reason":"PARAMETER_COUNT_NEAR_MATCH_DOES_NOT_ESTABLISH_EQUAL_EFFECTIVE_CAPACITY","cross_model_score_scale":"NOT_COMPARABLE","history_causal_attribution":"NOT_COMPARABLE","model_execution":"NOT_CHECKED","model_origin":"NOT_AUTHENTICATED","ranking":"NOT_PERFORMED","statistical_significance":"NOT_PERFORMED"};
export const CAPACITY_ENDPOINT = '/candidate/v1/capacity-comparison';
export const MAX_RESPONSE_BYTES = 1048576;
const POLICIES = ['P_U', 'P_B', 'P_A'];
const SLOTS = ['current_ae13', 'current_ae13_capacity492', 'history_ae26_h15', 'history_ae26_h30'];
const NAMES = ['当前特征（288参数）', '当前特征（492参数）', '历史15分钟（509参数）', '历史30分钟（509参数）'];
const OLD_VERIFIER = 'c17-i1-g13u-ae-run-verifier-v1';
const NEW_VERIFIER = 'c17-i1-g13u-ae-capacity-run-verifier-v1';
const COUNTS = ['calendar_test_minutes', 'scored_test_minutes', 'excluded_unscored_test_minutes', 'normal_minutes', 'attack_minutes', 'unknown_minutes', 'unknown_source_attack_present'];
const CONFUSION = ['tp', 'fp', 'tn', 'fn'];
const METRICS = ['precision', 'recall', 'f1', 'fpr', 'fnr'];
const ARTIFACTS = ['manifest.json', 'model-state.json', 'scores.json', 'evaluation.json', 'weights.json'];
const PROVENANCE = ['record_manifest', 'input_manifest', 'source_fixture', 'minute_fixture', 'preprocess'];
const NULL_REASONS = {
  precision: 'No positive predictions on scored normal or attack test minutes.',
  recall: 'No scored attack test minutes.',
  f1: 'No scored attack test minutes or positive predictions on scored labeled test minutes.',
  fpr: 'No scored normal test minutes.', fnr: 'No scored attack test minutes.',
};
const NULL_LABELS = { precision: '没有带标签的正预测分钟', recall: '没有已评分攻击分钟', f1: '没有已评分攻击或带标签的正预测分钟', fpr: '没有已评分正常分钟', fnr: '没有已评分攻击分钟' };
const ROOT_KEYS = ['schema_version', 'comparison_profile_id', 'status', 'evidence_kind', 'policy_status', 'scope', 'included_slots', 'missing_slots', 'shared_context', 'runs', 'control_design', 'limitations'];
const ROW_KEYS = ['slot', 'run_id', 'model_profile_id', 'verifier_profile_id', 'configuration', 'configuration_sha256', 'library_versions', 'runtime', 'architecture', 'parameter_count', 'parameter_count_reason', 'threshold', 'calibration', 'policies', 'actual_five_artifacts', 'verification_checks', 'verification_scope'];
const SHARED_KEYS = ['selected_policy', 'source_replay', 'feature_names', 'qualification_windows', 'five_provenance', 'preprocessing_identity', 'preprocessing_state', 'qualification_protocol', 'qualification_axis_identity', 'minute_count', 'score_valid_count', 'fit_count', 'calibration_count', 'test_denominators_by_policy'];
const ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;
const SHA = /^[a-f0-9]{64}$/;
const VERSION = /^[A-Za-z0-9][A-Za-z0-9._+!-]{0,63}$/;
function need(condition) { if (!condition) throw new Error('INVALID_CAPACITY_REPORT'); }
function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function keys(value, names) { need(object(value) && Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name))); }
function same(a, b) {
  if (typeof a !== typeof b || a === null || b === null) return Object.is(a, b);
  if (Array.isArray(a) || Array.isArray(b)) return Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((value, index) => same(value, b[index]));
  if (object(a)) return object(b) && Object.keys(a).length === Object.keys(b).length && Object.keys(b).every(key => Object.hasOwn(a, key) && same(a[key], b[key]));
  return Object.is(a, b);
}
function count(value, max = 10000, min = 0) { need(Number.isSafeInteger(value) && value >= min && value <= max); }
function finite(value, min = 0, max = Infinity) { need(typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max); }
function bounded(value, depth = 0, counter = { n: 0 }) {
  need(depth <= 16 && ++counter.n <= 20000);
  if (Array.isArray(value)) { need(value.length <= 10000); for (const child of value) bounded(child, depth + 1, counter); }
  else if (object(value)) {
    need(Object.keys(value).length <= 128);
    for (const [key, child] of Object.entries(value)) { need(key.length <= 128); bounded(child, depth + 1, counter); }
  } else if (typeof value === 'string') need(value.length <= 1024);
  else if (typeof value === 'number') need(Number.isFinite(value) && (!Number.isInteger(value) || Number.isSafeInteger(value)));
  else need(value === null || typeof value === 'boolean');
}
function identity(value, maximum = 16 * 1024 * 1024) {
  keys(value, ['sha256', 'byte_count']); need(typeof value.sha256 === 'string' && SHA.test(value.sha256)); count(value.byte_count, maximum, 1);
}
function population(value, context) {
  keys(value, COUNTS); for (const n of Object.values(value)) count(n);
  need(value.calendar_test_minutes <= context.minute_count && value.scored_test_minutes <= context.score_valid_count
    && value.calendar_test_minutes === value.scored_test_minutes + value.excluded_unscored_test_minutes
    && value.normal_minutes + value.attack_minutes + value.unknown_minutes === value.scored_test_minutes
    && value.unknown_source_attack_present <= value.unknown_minutes);
}

/** Display integrity checks only. This does not admit packages or authenticate training. */
export function validateCapacityReport(report) {
  bounded(report); keys(report, ROOT_KEYS);
  need(report.schema_version === 1 && report.comparison_profile_id === 'c17-i1-g13u-ae-capacity-comparison-context-v1'
    && report.status === 'DATA_QUALIFICATION_ALIGNED' && report.evidence_kind === 'SYNTHETIC_ONLY'
    && report.policy_status === 'AUDIT_ONLY' && report.scope === 'SYNTHETIC_STORED_COMPARISON_CONTEXT_ONLY');
  const slots = report.included_slots, rows = report.runs;
  need(Array.isArray(slots) && slots.every(slot => typeof slot === 'string') && new Set(slots).size === slots.length
    && same(slots, SLOTS.filter(slot => slots.includes(slot))) && same(report.missing_slots, SLOTS.filter(slot => !slots.includes(slot)))
    && slots.includes(SLOTS[1]) && (slots.includes(SLOTS[2]) || slots.includes(SLOTS[3]))
    && Array.isArray(rows) && rows.length >= 2 && rows.length <= 4 && rows.length === slots.length);
  const histories = SLOTS.slice(2).filter(slot => slots.includes(slot));
  need(same(report.control_design, {
    fixed_current_profile: FIXED_CONFIGURATIONS[SLOTS[1]].model_profile_id, reference_parameter_count: 509,
    parameter_count_formula: 'SUM_LINEAR_WEIGHTS_AND_BIASES_V1', no_history_input: true,
    near_count: { absolute_difference: 17, relative_difference: 17 / 509, tolerance: .05, status: 'PREDEFINED_COUNT_ONLY' },
    same_hidden_width_pairs: slots.includes(SLOTS[0]) ? histories.map(slot => [SLOTS[0], slot]) : [],
    near_parameter_count_pairs: histories.map(slot => [SLOTS[1], slot]),
    same_hidden_width_control_present: slots.includes(SLOTS[0]), controls_materials_complete: slots.length === 4,
  }));
  const shared = report.shared_context; keys(shared, SHARED_KEYS);
  need(POLICIES.includes(shared.selected_policy) && shared.source_replay === 'VERIFIED' && same(shared.feature_names, FIXED_FEATURES)
    && same(shared.qualification_windows, [15, 30]) && same(shared.qualification_protocol, FIXED_PROTOCOL));
  for (const name of ['minute_count', 'score_valid_count', 'fit_count', 'calibration_count']) count(shared[name], 10000, name === 'score_valid_count' ? 0 : 1);
  need(shared.score_valid_count <= shared.minute_count && shared.fit_count + shared.calibration_count <= shared.score_valid_count);
  identity(shared.qualification_axis_identity); identity(shared.preprocessing_identity); keys(shared.five_provenance, PROVENANCE);
  for (const value of Object.values(shared.five_provenance)) identity(value);
  need(same(shared.preprocessing_identity, shared.five_provenance.preprocess));
  const source = shared.five_provenance.source_fixture;
  need(same(source, { sha256: '6f42399eabb07dc218eac19f4d648e57eb360a0c7167968ca1770733ea8649b2', byte_count: 213497 })
    || same(source, { sha256: '0f8e58e6dec98c2741362f1a146d2721e40cce48dfe637c4708bcf9d21ef42ff', byte_count: 205567 }));
  const prep = shared.preprocessing_state;
  keys(prep, ['schema_version', 'profile_id', 'evidence_kind', 'transform', 'feature_names', 'mean', 'scale', 'n_samples_seen', 'fit_window']);
  need(prep.schema_version === 1 && prep.profile_id === 'c17-i1-g13u-candidate-v1' && prep.evidence_kind === 'SYNTHETIC_ONLY'
    && prep.transform === 'log1p_standard_ddof0' && same(prep.feature_names, FIXED_FEATURES) && prep.fit_window === 30);
  need(Array.isArray(prep.mean) && Array.isArray(prep.scale) && prep.mean.length === 13 && prep.scale.length === 13);
  prep.mean.forEach(value => finite(value, -Infinity)); prep.scale.forEach(value => { finite(value); need(value > 0); }); count(prep.n_samples_seen, 10000, 1);
  keys(shared.test_denominators_by_policy, POLICIES);
  Object.values(shared.test_denominators_by_policy).forEach(value => population(value, shared));
  const ids = new Set();
  rows.forEach((row, index) => {
    keys(row, ROW_KEYS); const slot = slots[index], cfg = FIXED_CONFIGURATIONS[slot];
    need(row.slot === slot && typeof row.run_id === 'string' && ID.test(row.run_id) && !ids.has(row.run_id)); ids.add(row.run_id);
    need(row.model_profile_id === cfg.model_profile_id && row.verifier_profile_id === (slot === SLOTS[1] ? NEW_VERIFIER : OLD_VERIFIER)
      && same(row.configuration, cfg) && row.configuration_sha256 === FIXED_CONFIGURATION_DIGESTS[slot]
      && same(row.architecture, cfg.architecture) && row.parameter_count === cfg.parameter_count && row.parameter_count_reason === null
      && row.verification_scope === 'STORED_ARTIFACT_CONSISTENCY_ONLY' && same(row.verification_checks, FIXED_CHECKS));
    keys(row.library_versions, ['python', 'numpy', 'torch']); need(Object.values(row.library_versions).every(value => typeof value === 'string' && VERSION.test(value)));
    keys(row.runtime, ['device', 'torch_num_threads', 'torch_num_interop_threads']); need(row.runtime.device === 'cpu');
    count(row.runtime.torch_num_threads, 2147483647, 1); count(row.runtime.torch_num_interop_threads, 2147483647, 1);
    keys(row.actual_five_artifacts, ARTIFACTS);
    for (const name of ARTIFACTS) identity(row.actual_five_artifacts[name], name === 'weights.json' ? 1048576 : 16 * 1048576);
    need(Object.values(row.actual_five_artifacts).reduce((sum, value) => sum + value.byte_count, 0) <= 32 * 1048576);
    finite(row.threshold); const cal = row.calibration;
    keys(cal, ['sample_count', 'quantile', 'method', 'comparison', 'order_position_zero_based', 'strictly_above_count', 'equal_count']);
    need(cal.quantile === .99 && cal.method === 'linear' && cal.comparison === 'STRICT_GREATER' && cal.sample_count === shared.calibration_count);
    count(cal.sample_count, 10000, 1); finite(cal.order_position_zero_based, 0, cal.sample_count);
    count(cal.strictly_above_count, cal.sample_count); count(cal.equal_count, cal.sample_count); need(cal.strictly_above_count + cal.equal_count <= cal.sample_count);
    keys(row.policies, POLICIES);
    for (const name of POLICIES) {
      const p = row.policies[name]; keys(p, [...COUNTS, 'confusion_counts', 'metrics', 'undefined_reasons']);
      need(COUNTS.every(key => p[key] === shared.test_denominators_by_policy[name][key]));
      const c = p.confusion_counts; keys(c, CONFUSION); Object.values(c).forEach(value => count(value));
      need(c.tp + c.fn === p.attack_minutes && c.fp + c.tn === p.normal_minutes);
      keys(p.metrics, METRICS); Object.values(p.metrics).forEach(value => { if (value !== null) finite(value, 0, 1); });
      // Check the saved definition domain, never recompute a metric ratio.
      const denominators = [c.tp + c.fp, c.tp + c.fn, 2 * c.tp + c.fp + c.fn, c.fp + c.tn, c.tp + c.fn];
      need(METRICS.every((key, i) => (p.metrics[key] === null) === (denominators[i] === 0)));
      need(same(p.undefined_reasons, Object.fromEntries(METRICS.filter(key => p.metrics[key] === null).map(key => [key, NULL_REASONS[key]]))));
    }
  });
  const limits = report.limitations; keys(limits, [...Object.keys(FIXED_LIMITATIONS), 'execution_controls']);
  need(Object.keys(FIXED_LIMITATIONS).every(key => same(limits[key], FIXED_LIMITATIONS[key])));
  const equalControls = rows.every(row => same(row.library_versions, rows[0].library_versions) && same(row.runtime, rows[0].runtime));
  need(limits.execution_controls === (equalControls ? 'SHARED_DECLARATIONS_CONSISTENT_ONLY' : 'DECLARED_EXECUTION_CONTROLS_DIFFER'));
  return report;
}

/** Bound received bytes, including whitespace/LF, without trusting Content-Length. */
export async function readCapacityResponse(response, signal) {
  if (!response?.ok) { try { void response?.body?.cancel().catch(() => {}); } catch {} throw new Error('FETCH_FAILED'); }
  if (!response.body || typeof response.body.getReader !== 'function') throw new Error('INVALID_CAPACITY_REPORT');
  const reader = response.body.getReader(), chunks = []; let total = 0;
  const cancel = () => { try { void reader.cancel().catch(() => {}); } catch {} };
  signal.addEventListener('abort', cancel, { once: true });
  try {
    while (true) {
      if (signal.aborted) throw new Error('CANCELLED');
      const { done, value } = await reader.read();
      if (signal.aborted) throw new Error('CANCELLED');
      if (done) break;
      if (!ArrayBuffer.isView(value) || Object.prototype.toString.call(value) !== '[object Uint8Array]') throw new Error('INVALID_CAPACITY_REPORT');
      total += value.byteLength;
      if (total > MAX_RESPONSE_BYTES) throw new Error('RESOURCE_LIMIT');
      chunks.push(value);
    }
    const bytes = new Uint8Array(total); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes));
  } catch (error) { cancel(); throw error; }
  finally { signal.removeEventListener('abort', cancel); reader.releaseLock(); }
}

const LAYOUT = `
<p class="eyebrow">人工样例 · 参数数量对照</p><h1>当前与历史模型对照</h1>
<p class="notice">仅展示已保存的人工工程结果；未认证训练来源，不构成真实检测效果或历史因果结论。</p>
<section class="panel" aria-labelledby="capacity-title"><h2 id="capacity-title">保存的模型与评价</h2>
<div class="controls"><label>查看已保存口径<select id="capacity-policy" disabled><option value="P_U">口径 P_U</option><option value="P_B">口径 P_B</option><option value="P_A">口径 P_A</option></select></label><button id="capacity-retry" class="secondary">重新读取</button></div>
<p class="muted">口径切换只查看原保存值，不改变分数来源口径、阈值或预测。</p>
<p id="capacity-status" class="status" role="status" aria-live="polite"></p><p id="capacity-error" class="error" role="alert"></p>
<p id="capacity-context"></p><p id="capacity-population"></p><p id="capacity-completeness" class="muted"></p>
<div id="capacity-table" class="table-scroll comparison-table" role="region" tabindex="0" aria-label="模型容量对照表，窄屏可横向滚动"></div>
<p class="muted">误报率 FPR 的分母是已评分正常分钟（FP+TN）；漏报率 FNR 的分母是已评分攻击分钟（TP+FN）。未知与未评分分钟分别列出，不混入分母。不可评价保留原原因，不填成零。</p>
<p class="muted">每个模型使用自己的共同校准人口分数，以 Q99 / linear 保存阈值；严格高于阈值才报警。阈值可不同，不能据其大小比较跨模型评分尺度。</p></section>
<section class="panel"><h2>参数数量怎样理解</h2><p>492 与 509 相差 17 个参数；以 509 为参照约 3.34%（17/509）。预设的参数数量接近范围为 5%，不代表有效容量相同。</p><p id="capacity-pairs"></p><p class="muted">只展示预设对照关系，不进行排名、不推断历史信息改善效果，也不作统计显著性结论。</p></section>
<section id="capacity-evidence" class="panel" aria-label="保存证据与原始数值"></section>`;
function element(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
const numeric = value => Object.is(value, -0) ? '-0' : String(value);
const rate = (value, key) => value === null ? `不可评价（${NULL_LABELS[key]}）` : `${(value * 100).toFixed(1)}%`;
const label = slot => NAMES[SLOTS.indexOf(slot)];
function errorMessage(error) {
  if (error?.message === 'RESOURCE_LIMIT') return '报告超过读取上限，未显示部分结果。';
  if (['INVALID_CAPACITY_REPORT', 'SyntaxError', 'TypeError'].includes(error?.message) || error instanceof SyntaxError) return '报告格式不匹配，请确认服务版本。';
  return '读取失败，请检查服务后重试。';
}
export function mountCapacityViewer(root, { fetcher = globalThis.fetch.bind(globalThis) } = {}) {
  root.innerHTML = LAYOUT; // Fixed local layout; all response values use textContent.
  const refs = new Map([...root.querySelectorAll('[id]')].map(node => [node.id, node]));
  const get = id => refs.get(id), text = (id, value) => { get(id).textContent = value; };
  let generation = 0, controller, disposed = false, report = null;
  function clear() {
    report = null; for (const id of ['capacity-context', 'capacity-population', 'capacity-completeness', 'capacity-pairs', 'capacity-error']) text(id, '');
    get('capacity-table').replaceChildren(); get('capacity-evidence').replaceChildren(); get('capacity-policy').disabled = true;
  }
  function render() {
    const p = get('capacity-policy').value, s = report.shared_context, population = s.test_denominators_by_policy[p];
    text('capacity-context', `来源与保存关系已核对（不认证训练来源）· 分数来源口径 ${s.selected_policy} · 全轴 ${s.minute_count} / 全轴可评分 ${s.score_valid_count} / 拟合 ${s.fit_count} / 校准 ${s.calibration_count} 分钟`);
    text('capacity-population', `${p} · 完整测试 ${population.calendar_test_minutes} 分钟 · 可评分 ${population.scored_test_minutes} · 未评分 ${population.excluded_unscored_test_minutes} · 正常 ${population.normal_minutes} · 攻击 ${population.attack_minutes} · 未知 ${population.unknown_minutes}（其中原攻击标签存在 ${population.unknown_source_attack_present}）`);
    text('capacity-completeness', report.missing_slots.length ? `材料缺少：${report.missing_slots.map(label).join('、')}。未提供的运行不会补跑或补值。` : '四槽材料齐全，仅表示本次人工对照材料齐全。');
    const table = element('table'), head = element('thead'), header = element('tr'), body = element('tbody');
    table.append(element('caption', `${p} · 已保存逐分钟评价；比率为百分数显示，原值见证据。`));
    for (const name of ['模型', '各自阈值', 'TP', 'FP', 'TN', 'FN', '误报率 FPR', '漏报率 FNR']) { const th = element('th', name); th.scope = 'col'; header.append(th); }
    head.append(header); table.append(head);
    for (const slot of SLOTS) {
      const tr = element('tr'), th = element('th', label(slot)); tr.dataset.slot = slot; th.scope = 'row'; tr.append(th);
      const saved = report.runs.find(row => row.slot === slot);
      if (!saved) { const missing = element('td', '未提供此运行包'); missing.colSpan = 7; tr.append(missing); }
      else {
        const values = saved.policies[p]; tr.append(element('td', numeric(saved.threshold)));
        for (const key of CONFUSION) tr.append(element('td', numeric(values.confusion_counts[key])));
        tr.append(element('td', rate(values.metrics.fpr, 'fpr')), element('td', rate(values.metrics.fnr, 'fnr')));
      }
      body.append(tr);
    }
    table.append(body); get('capacity-table').replaceChildren(table);
    const design = report.control_design, pairs = [];
    if (design.same_hidden_width_pairs.length) pairs.push('相同隐藏宽度：' + design.same_hidden_width_pairs.map(pair => pair.map(label).join(' ↔ ')).join('；'));
    pairs.push('参数数量接近：' + design.near_parameter_count_pairs.map(pair => pair.map(label).join(' ↔ ')).join('；'));
    text('capacity-pairs', pairs.join('。'));
  }
  function evidence() {
    const container = get('capacity-evidence'); container.replaceChildren();
    for (const row of report.runs) {
      const details = element('details'); details.append(element('summary', `${label(row.slot)} · 保存详情`));
      details.append(element('p', `运行 ${row.run_id} · 输入/架构 ${row.architecture.join(' → ')} · 参数 ${row.parameter_count}`, 'mono'));
      details.append(element('p', `本方法保存阈值 ${numeric(row.threshold)} · 校准 ${row.calibration.sample_count} 分钟 · 等于阈值 ${row.calibration.equal_count} / 严格高于 ${row.calibration.strictly_above_count}。`));
      for (const policy of POLICIES) {
        const saved = row.policies[policy]; details.append(element('p', `${policy} 精确率 ${rate(saved.metrics.precision, 'precision')} · 召回率 ${rate(saved.metrics.recall, 'recall')} · F1 ${rate(saved.metrics.f1, 'f1')}`));
      }
      container.append(details);
    }
    const all = element('details'); all.append(element('summary', '查看全部保存证据与原始数值'));
    all.append(element('p', '下列标识和验证状态来自保存报告。页面校验仅保护显示，不认证训练执行或模型来源。', 'muted'), element('pre', JSON.stringify(report, null, 2), 'mono')); container.append(all);
  }
  async function reload() {
    const version = ++generation; controller?.abort(); controller = new AbortController(); clear(); text('capacity-status', '读取中…');
    const signal = controller.signal;
    try {
      const response = await fetcher(CAPACITY_ENDPOINT, { method: 'GET', signal, credentials: 'same-origin', redirect: 'error' });
      if (disposed || version !== generation) { try { void response?.body?.cancel().catch(() => {}); } catch {} return; }
      const value = await readCapacityResponse(response, signal);
      if (disposed || version !== generation) return;
      report = validateCapacityReport(value); render(); evidence(); get('capacity-policy').disabled = false;
    } catch (error) { if (!disposed && version === generation) { clear(); text('capacity-error', errorMessage(error)); } }
    finally { if (!disposed && version === generation) text('capacity-status', ''); }
  }
  get('capacity-retry').addEventListener('click', () => { void reload(); });
  get('capacity-policy').addEventListener('change', () => { if (report && POLICIES.includes(get('capacity-policy').value)) render(); });
  void reload();
  return { reload, dispose() { disposed = true; generation++; controller?.abort(); report = null; root.replaceChildren(); } };
}
const root = typeof document === 'undefined' ? null : document.getElementById('capacity-viewer');
if (root) mountCapacityViewer(root);
