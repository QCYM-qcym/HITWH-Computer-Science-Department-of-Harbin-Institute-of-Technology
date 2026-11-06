import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// Display-boundary fixtures only. They do not load runs, train models, or
// establish saved-artifact authenticity. No Task14–16 consumer is implemented.
const classicProfile = 'c17-i1-g13u-ae-synthetic-v1'
const capacityProfile = 'c17-i1-g13u-ae-current-capacity492-synthetic-v1'
const classicSlots = ['iforest_current13', 'current_ae13', 'history_ae26_h15', 'history_ae26_h30']
const populations = ['calendar_test_minutes', 'scored_test_minutes', 'excluded_unscored_test_minutes',
  'normal_minutes', 'attack_minutes', 'unknown_minutes', 'unknown_source_attack_present'] as const
const metricNames = ['precision', 'recall', 'f1', 'fpr', 'fnr'] as const
type Metric = typeof metricNames[number]

function policies() {
  const unknownReasons = Object.fromEntries(metricNames.map(key => [key, `Saved ${key} unavailable: no labelled population.`]))
  return {
    P_U: { calendar_test_minutes: 36, scored_test_minutes: 6, excluded_unscored_test_minutes: 30,
      normal_minutes: 0, attack_minutes: 0, unknown_minutes: 6, unknown_source_attack_present: 2,
      confusion_counts: { tp: 0, fp: 0, tn: 0, fn: 0 },
      metrics: Object.fromEntries(metricNames.map(key => [key, null])) as Record<Metric, number | null>, undefined_reasons: unknownReasons },
    P_B: { calendar_test_minutes: 36, scored_test_minutes: 6, excluded_unscored_test_minutes: 30,
      normal_minutes: 4, attack_minutes: 2, unknown_minutes: 0, unknown_source_attack_present: 0,
      confusion_counts: { tp: 1, fp: 0, tn: 4, fn: 1 },
      metrics: { precision: 1, recall: 0.5, f1: 2 / 3, fpr: 0, fnr: 0.5 }, undefined_reasons: {} },
    P_A: { calendar_test_minutes: 36, scored_test_minutes: 6, excluded_unscored_test_minutes: 30,
      normal_minutes: 2, attack_minutes: 4, unknown_minutes: 0, unknown_source_attack_present: 0,
      confusion_counts: { tp: 2, fp: 1, tn: 1, fn: 2 },
      metrics: { precision: 2 / 3, recall: 0.5, f1: 4 / 7, fpr: 0.5, fnr: 0.5 }, undefined_reasons: {} },
  }
}

function fixture() {
  const items = [
    { run_id: 'classic-current', model_profile_id: classicProfile, method: 'current_ae', history_window: null },
    { run_id: 'classic-h30', model_profile_id: classicProfile, method: 'history_ae', history_window: 30 },
  ].map(item => ({ ...item, selected_policy: 'P_U', minute_count: 144, score_valid_count: 24,
    source_replay: { run: 'NOT_PROVIDED', inputs: 'NOT_PROVIDED', combined: 'NOT_PROVIDED' } }))
  const p = policies()
  return {
    catalog: { schema_version: 1, evidence_kind: 'SYNTHETIC_ONLY', policy_status: 'AUDIT_ONLY',
      scope: 'SYNTHETIC_SAVED_RUN_INSPECTION_ONLY', comparison_available: true, items },
    comparison: {
      schema_version: 1, comparison_profile_id: 'c17-i1-g13u-comparison-context-v1',
      status: 'DATA_QUALIFICATION_ALIGNED', evidence_kind: 'SYNTHETIC_ONLY', policy_status: 'AUDIT_ONLY',
      scope: 'SYNTHETIC_STORED_COMPARISON_CONTEXT_ONLY', included_slots: [classicSlots[1], classicSlots[3]],
      missing_slots: [classicSlots[0], classicSlots[2]],
      shared_context: { selected_policy: 'P_U', source_replay: 'NOT_PROVIDED', minute_count: 144,
        score_valid_count: 24, fit_count: 6, calibration_count: 6, qualification_windows: [15, 30],
        test_denominators_by_policy: Object.fromEntries(Object.entries(p).map(([name, value]) =>
          [name, Object.fromEntries(populations.map(key => [key, value[key]]))])) },
      limitations: { capacity_control: 'NOT_COMPARABLE', history_causal_attribution: 'NOT_COMPARABLE',
        cross_model_score_scale: 'NOT_COMPARABLE', ranking: 'NOT_PERFORMED', statistical_significance: 'NOT_PERFORMED',
        model_execution: 'NOT_CHECKED', model_origin: 'NOT_AUTHENTICATED', execution_controls: 'SHARED_DECLARATIONS_CONSISTENT_ONLY' },
      runs: items.map((item, i) => ({ slot: classicSlots[i ? 3 : 1]!, run_id: item.run_id, model_profile_id: item.model_profile_id,
        parameter_count: i ? 509 : 288, parameter_count_reason: null, architecture: i ? [26, 8, 3, 8, 26] : [13, 8, 3, 8, 13],
        configuration: { input_width: i ? 26 : 13, parameter_status: 'ENGINEERING_TOY_ONLY',
          method: item.method, history_window: item.history_window, score_rule: 'FLOAT64_CHANNEL_MSE_EQUAL_WEIGHT' },
        threshold: i ? 0.375 : 0,
        calibration: { sample_count: 6, quantile: 0.99, method: 'linear', comparison: 'STRICT_GREATER',
          order_position_zero_based: 4.95, strictly_above_count: 0, equal_count: 1 },
        policies: structuredClone(p), verification_scope: 'STORED_ARTIFACT_CONSISTENCY_ONLY',
        verification_checks: { source_replay: 'NOT_PROVIDED' },
        actual_five_artifacts: Object.fromEntries(['manifest.json', 'model-state.json', 'scores.json', 'evaluation.json', 'weights.json']
          .map(name => [name, { sha256: 'a'.repeat(64), byte_count: 128 }])) })),
    },
  }
}

let modulePromise: Promise<{ mountViewer: (root: HTMLElement, options: { fetcher: (url: string) => Promise<unknown> }) => { dispose: () => void } }>
let handle: { dispose: () => void } | undefined
const el = (id: string) => document.getElementById(id)!
async function tick() { for (let i = 0; i < 24; i++) await Promise.resolve() }
async function mount(value: ReturnType<typeof fixture>, mutateOnRetry?: () => void) {
  const path = resolve(dirname(fileURLToPath(import.meta.url)), '../../../backend/traffic_api/candidate_static/viewer.mjs')
  modulePromise ??= import(/* @vite-ignore */ `data:text/javascript;base64,${Buffer.from(readFileSync(path)).toString('base64')}`)
  const root = document.createElement('main'); document.body.append(root)
  let comparisons = 0
  handle = (await modulePromise).mountViewer(root, { fetcher: async url => {
    if (url === '/candidate/v1/comparison' && comparisons++ > 0) mutateOnRetry?.()
    if (url === '/candidate/v1/runs') return { ok: true, json: async () => structuredClone(value.catalog) }
    if (url === '/candidate/v1/comparison') return { ok: true, json: async () => structuredClone(value.comparison) }
    throw new Error('No model, series or arbitrary resource is part of this boundary test')
  } })
  await tick()
  return root
}

beforeEach(() => document.body.replaceChildren())
afterEach(() => { handle?.dispose(); handle = undefined })

describe('classic viewer compatibility before capacity consumer implementation', () => {
  it('keeps missing slots, saved null reasons, own zero/nonzero thresholds and fixed order without choosing a winner', async () => {
    const value = fixture(), root = await mount(value)
    expect(el('comparison-error').textContent).toBe('')
    const rows = [...el('comparison-table').querySelectorAll('tbody tr')]
    expect(rows.map(row => (row as HTMLElement).dataset.slot)).toEqual(classicSlots)
    expect(rows[0]!.textContent).toContain('未提供'); expect(rows[2]!.textContent).toContain('未提供')
    expect(rows[1]!.textContent).toContain('Saved fpr unavailable'); expect(rows[1]!.textContent).toContain('未定义')
    expect(el('comparison-details').querySelectorAll('details')[0]!.textContent).toContain('保存阈值 0（仅用于本方法）')
    expect(el('comparison-details').querySelectorAll('details')[1]!.textContent).toContain('保存阈值 0.375（仅用于本方法）')
    const selector = el('comparison-policy') as HTMLSelectElement
    selector.value = 'P_B'; selector.dispatchEvent(new Event('change')); await tick()
    const currentCells = [...el('comparison-table').querySelectorAll('tbody tr')[1]!.children]
    expect(currentCells.at(-2)!.textContent).toBe('0')
    expect(currentCells.at(-1)!.textContent).toBe('0.5')
    expect(el('comparison-population').textContent).toContain('测试日历分钟 36 / 测试可评分 6 / 排除未评分 30')
    expect(el('comparison-context').textContent).toContain('全轴 144 / 全轴可评分 24')
    expect(root.textContent).toContain('不能据此排名')
    expect(value.comparison.runs.map(row => row.threshold)).toEqual([0, 0.375])
  })

  it.each(['capacity-envelope', 'capacity-slot', 'capacity492-as-classic-current'])('rejects %s rather than relabeling it as old current288', async kind => {
    const value = fixture(), row = value.comparison.runs[0]!
    if (kind === 'capacity-envelope') value.comparison.comparison_profile_id = 'c17-i1-g13u-ae-capacity-comparison-context-v1'
    if (kind === 'capacity-slot') { row.slot = 'current_ae13_capacity492'; value.comparison.included_slots[0] = row.slot }
    if (kind === 'capacity492-as-classic-current') {
      value.catalog.items[0]!.model_profile_id = capacityProfile; row.model_profile_id = capacityProfile
      row.parameter_count = 492; row.architecture = [13, 14, 3, 14, 13]
    }
    await mount(value)
    expect(el('comparison-error').textContent).toContain('格式不匹配')
    expect(el('comparison-table').children).toHaveLength(0)
    expect(el('comparison-details').children).toHaveLength(0)
  })

  it('removes prior classic success if retry receives a capacity payload', async () => {
    const value = fixture()
    await mount(value, () => { value.comparison.comparison_profile_id = 'c17-i1-g13u-ae-capacity-comparison-context-v1' })
    expect(el('comparison-table').querySelectorAll('tbody tr')).toHaveLength(4)
    el('retry-comparison').click(); await tick()
    expect(el('comparison-error').textContent).toContain('格式不匹配')
    expect(el('comparison-table').children).toHaveLength(0)
    expect(el('comparison-context').textContent).toBe('')
  })
})
