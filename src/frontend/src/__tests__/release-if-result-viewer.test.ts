import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { webcrypto } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../backend/traffic_api/release_if_static')
const FILE = resolve(DIR, 'results.mjs')
const Q = 'c17-release-iforest-view-v1', SCOPE = 'SAVED_RESULT_INTERNAL_CONSISTENCY_ONLY'
const H = 'a'.repeat(64)
// SHA256 of the independently written canonical profile + two result identities, including LF.
const SNAPSHOT = 'ebd59b17d4f48d432a5dc6bb2023c1bc97bc09331e4de7d0298464e8fe0eab90'
const identity = (profile: string, hash = H) => ({ profile_id: profile, context_sha256: hash, manifest_sha256: hash, manifest_byte_count: 1234 })
const config = (width: number) => ({ input_width: width, n_estimators: 16, max_samples: 2,
  max_features: 1, bootstrap: false, contamination: 'auto', random_state: 42, n_jobs: 1 })
// Complete, hand-specified protocol fixture. No product projection/model is used.
function summary(): any {
  return { version: 1, profile_id: Q, scope: SCOPE, snapshot_sha256: SNAPSHOT,
    source: { schema_id: 'c17-release-91-v1', authentication: 'NOT_AUTHENTICATED',
      time_basis: 'SOURCE_WALL_CLOCK_COMPLETION_PROXY', policy_status: 'AUDIT_ONLY', audit_fit_policy: 'P_U' },
    input_references: { raw: identity('c17-release-minute-package-v1'), prepared: identity('c17-release-prepared-input-package-v1'), configuration_sha256: H },
    result_references: { current13: identity('c17-release-iforest-result-package-v1', 'b'.repeat(64)), h30_26: identity('c17-release-iforest-result-package-v1', 'c'.repeat(64)) },
    axis: { minute_count: 201, scored_count: 6, unscored_count: 195, page_size: 100, page_count: 3,
      segments: [
        { ordinal: 0, id: '训练', role: 'train', start: '2020-01-01T00:00:00', end: '2020-01-01T01:40:00', minute_count: 100, scored_count: 2 },
        { ordinal: 1, id: '校准', role: 'calibration', start: '2020-01-02T00:00:00', end: '2020-01-02T01:40:00', minute_count: 100, scored_count: 4 },
        { ordinal: 2, id: '测试', role: 'test', start: '2020-01-03T00:00:00', end: '2020-01-03T00:01:00', minute_count: 1, scored_count: 0 },
      ] },
    views: { current13: { configuration: config(13), threshold: 1, training_count: 2, calibration_count: 4,
      preprocessing_fit_count: 3, equal_threshold_count: 3, above_threshold_count: 0 },
    h30_26: { configuration: config(26), threshold: 2, training_count: 2, calibration_count: 4,
      preprocessing_fit_count: 3, equal_threshold_count: 3, above_threshold_count: 0 } },
    checks: { internal_consistency: 'MATCHED', saved_score_q99: 'MATCHED', cross_view_binding: 'MATCHED',
      input_pair_binding: 'NOT_PERFORMED', source_authentication: 'NOT_AUTHENTICATED', model_execution: 'NOT_AUTHENTICATED' } }
}
function page(number = 0): any {
  const items = Array.from({ length: number === 2 ? 1 : 100 }, (_, local) => {
    const index = number * 100 + local
    const timestamp = `2020-01-0${number + 1}T${String(Math.floor(local / 60)).padStart(2, '0')}:${String(local % 60).padStart(2, '0')}:00`
    const scored = number === 0 ? [30, 31].includes(local) : number === 1 && [30, 31, 32, 33].includes(local)
    const a = number === 0 ? (local === 30 ? 0 : 4) : (local === 30 ? 0 : 1)
    const b = number === 0 ? (local === 30 ? 0 : 8) : (local === 30 ? 0 : 2)
    return { index, timestamp, segment_id: ['训练', '校准', '测试'][number], role: ['train', 'calibration', 'test'][number],
      break_before: !scored || local === 30, scored,
      current13: { score: scored ? a : null, prediction: scored ? a > 1 : null },
      h30_26: { score: scored ? b : null, prediction: scored ? b > 2 : null }, reason: scored ? null : 'NOT_SCORED_CAUSE_NOT_SAVED' }
  })
  return { version: 1, profile_id: Q, scope: SCOPE, snapshot_sha256: SNAPSHOT, page: number, page_size: 100,
    total: 201, returned: items.length, items }
}
const bytes = (x: unknown) => new TextEncoder().encode(JSON.stringify(x) + '\n')
const response = (x: unknown, headers = {}) => new Response(bytes(x), { headers: { 'Content-Type': 'application/json', ...headers } })
function deferred<T>() { let resolve!: (x: T) => void, reject!: (x: unknown) => void
  const promise = new Promise<T>((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
let modulePromise: Promise<any> | undefined
async function api() {
  expect(existsSync(FILE), 'independent saved-result module must exist').toBe(true)
  return modulePromise ??= import(/* @vite-ignore */ `data:text/javascript;base64,${Buffer.from(readFileSync(FILE)).toString('base64')}`)
}
// jsdom has no SubtleCrypto. Await the actual platform digest as well as the fetch/stream microtasks.
let lastDigest: Promise<ArrayBuffer> | undefined
beforeEach(() => {
  lastDigest = undefined
  vi.stubGlobal('crypto', webcrypto)
  const digest = webcrypto.subtle.digest.bind(webcrypto.subtle)
  vi.spyOn(webcrypto.subtle, 'digest').mockImplementation((...args) => lastDigest = digest(...args))
})
async function flush() {
  for (let i = 0; i < 100; i++) await Promise.resolve()
  await lastDigest
  for (let i = 0; i < 100; i++) await Promise.resolve()
}
type Handle = { destroy(): void }
const handles: Handle[] = []
type Fetcher = (url: string, init: RequestInit) => Promise<unknown>
async function mount(fetchImpl: Fetcher = async url => response(url.endsWith('summary') ? summary() : page(Number(url.split('=')[1]))), options = {}) {
  const m = await api(), root = document.createElement('main'); document.body.append(root)
  const handle = m.mountReleaseIFResultView(root, { fetchImpl, ...options }); handles.push(handle); await flush()
  return { root, handle }
}
function click(root: HTMLElement, action: string) { (root.querySelector(`[data-action="${action}"]`) as HTMLButtonElement).click() }
function error(root: HTMLElement) { return root.querySelector('[role="alert"]')?.textContent ?? '' }
afterEach(() => { for (const h of handles.splice(0)) h.destroy(); document.body.replaceChildren(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('independent saved IF result consumer', () => {
  it('keeps both saved views, zero/false/null, full identities and calibration-only counts', async () => {
    const calls: string[] = [], { root } = await mount(async url => { calls.push(url); return response(url.endsWith('summary') ? summary() : page()) })
    expect(error(root)).toBe('')
    expect(calls).toEqual(['/release-if/v1/summary', '/release-if/v1/series?page=0'])
    expect(root.querySelectorAll('[data-view-card]')).toHaveLength(2)
    expect(root.querySelectorAll('svg')).toHaveLength(2)
    expect(root.querySelectorAll('tbody tr')).toHaveLength(100)
    expect(root.querySelector('[data-index="30"]')?.textContent).toContain('0未报警')
    expect(root.querySelector('[data-index="31"]')?.textContent).toContain('4报警')
    expect(root.querySelector('[data-index="0"]')?.textContent).toContain('未评分，包内未保存具体原因')
    for (const text of [H, SNAPSHOT, 'b'.repeat(64), 'c'.repeat(64), 'NOT_AUTHENTICATED', 'AUDIT_ONLY', '非认证 UTC',
      '预处理拟合分钟', '模型训练分钟', '独立校准分钟', '校准分钟中等于阈值', '校准分钟中严格超过阈值', 'role=train']) expect(root.textContent).toContain(text)
    expect(root.querySelector('[data-view-card="current13"] [data-metric="above_threshold_count"]')?.textContent).toBe('0')
    expect(root.querySelector('[data-action="previous"]')?.hasAttribute('disabled')).toBe(true)
    expect(root.querySelector('[role="region"]')?.getAttribute('tabindex')).toBe('0')
    expect(root.querySelector('[role="status"]')?.getAttribute('aria-live')).toBe('polite')
    expect(root.textContent).not.toMatch(/准确率|误报率|正常|SYNTHETIC_ONLY/)
  })

  it('pages over the complete axis and keeps populations fixed, including the unscored final page', async () => {
    const { root } = await mount()
    click(root, 'next'); await flush()
    expect(root.querySelectorAll('tbody tr')).toHaveLength(100)
    expect(root.querySelector('tbody tr')?.getAttribute('data-index')).toBe('100')
    expect(root.querySelector('[data-view-card="current13"] [data-metric="training_count"]')?.textContent).toBe('2')
    click(root, 'next'); await flush()
    expect(root.querySelectorAll('tbody tr')).toHaveLength(1)
    expect(root.querySelector('tbody tr')?.getAttribute('data-index')).toBe('200')
    expect(root.querySelector('[data-action="next"]')?.hasAttribute('disabled')).toBe(true)
  })

  it.each(['current13', 'h30_26'])('rejects a well-formed substituted %s identity before requesting a page', async view => {
    const s = summary(), calls: string[] = []
    s.result_references[view].manifest_byte_count++
    const { root } = await mount(async url => {
      calls.push(url)
      return response(url.endsWith('summary') ? s : page())
    })
    expect(calls).toEqual(['/release-if/v1/summary'])
    expect(root.querySelectorAll('[data-view-card],svg,tbody tr')).toHaveLength(0)
    expect(root.querySelector('[data-action="retry-summary"]')).not.toBeNull()
  })

  it('offers summary retry if the platform cannot verify the digest', async () => {
    vi.stubGlobal('crypto', {})
    const { root } = await mount()
    expect(root.querySelector('[data-action="retry-summary"]')).not.toBeNull()
    expect(root.querySelectorAll('[data-view-card],svg')).toHaveLength(0)
  })

  it.each(['timeout', 'destroy'])('ignores late identity verification after %s', async action => {
    vi.useFakeTimers()
    const pending = deferred<ArrayBuffer>(), calls: string[] = []
    const validDigest = Uint8Array.from(Buffer.from(SNAPSHOT, 'hex')).buffer
    vi.mocked(webcrypto.subtle.digest).mockImplementationOnce(() => pending.promise)
    const { root, handle } = await mount(async url => {
      calls.push(url)
      return response(url.endsWith('summary') ? summary() : page())
    })
    expect(root.dataset.state).toBe('loading-summary')
    if (action === 'destroy') handle.destroy()
    else {
      await vi.advanceTimersByTimeAsync(10000)
      expect(error(root)).toContain('读取超时')
    }
    const snapshot = root.textContent
    pending.resolve(validDigest); await flush()
    expect(root.textContent).toBe(snapshot)
    expect(calls).toEqual(['/release-if/v1/summary'])
    expect(vi.getTimerCount()).toBe(0)
  })

  it.each(['summary', 'series'])('rejects raw 1e400 in %s', async target => {
    const s = summary(), p = page()
    if (target === 'summary') s.views.current13.threshold = 'OVERFLOW'
    else p.items[31].current13.score = 'OVERFLOW' // Already predicted true, consistent with +Infinity.
    const { root } = await mount(async url => new Response(
      JSON.stringify(url.endsWith('summary') ? s : p).replace('"OVERFLOW"', '1e400'),
      { headers: { 'Content-Type': 'application/json' } }))
    expect(error(root)).toContain('格式不匹配')
    expect(root.querySelectorAll('svg,tbody tr')).toHaveLength(0)
    expect(root.querySelector(`[data-action="retry-${target === 'summary' ? 'summary' : 'page'}"]`)).not.toBeNull()
  })

  it.each([
    ['missing view', (s: any) => { delete s.views.h30_26 }],
    ['extra shape', (s: any) => { s.axis.private = 'PRIVATE_TOKEN' }],
    ['count conservation', (s: any) => { s.axis.scored_count = 7 }],
    ['population mismatch', (s: any) => { s.views.h30_26.training_count = 3 }],
    ['calibration-only count', (s: any) => { s.views.current13.equal_threshold_count = 5 }],
    ['bad hash', (s: any) => { s.result_references.current13.context_sha256 = '<img src=x>' }],
    ['overlong ID', (s: any) => { s.axis.segments[0].id = '😀'.repeat(129) }],
    ['surrogate ID', (s: any) => { s.axis.segments[0].id = '\ud800' }],
    ['control ID', (s: any) => { s.axis.segments[0].id = 'bad\u007f' }],
    ['invalid timestamp', (s: any) => { s.axis.segments[0].start = '2020-02-30T00:00:00' }],
    ['unsupported trust', (s: any) => { s.checks.model_execution = 'AUTHENTICATED' }],
    ['identity bytes limit', (s: any) => { s.input_references.raw.manifest_byte_count = 65537 }],
    ['identity profile', (s: any) => { s.input_references.prepared.profile_id = 'other' }],
    ['identity boolean', (s: any) => { s.result_references.current13.manifest_byte_count = true }],
    ['threshold string', (s: any) => { s.views.current13.threshold = '1' }],
    ['null threshold', (s: any) => { s.views.current13.threshold = null }],
    ['zero calibration', (s: any) => { s.views.current13.calibration_count = 0 }],
    ['fit smaller than model training', (s: any) => { s.views.current13.preprocessing_fit_count = 1 }],
    ['fit beyond train partition', (s: any) => { s.views.current13.preprocessing_fit_count = 101 }],
    ['configuration width', (s: any) => { s.views.h30_26.configuration.input_width = 13 }],
    ['configuration fixed seed', (s: any) => { s.views.current13.configuration.random_state = 43 }],
    ['summary page count', (s: any) => { s.axis.page_count = 2 }],
    ['oversized axis', (s: any) => { s.axis.minute_count = 10001 }],
    ['segment count before traversal', (s: any) => { s.axis.segments = Array(8).fill(null) }],
    ['duplicate segment ID', (s: any) => { s.axis.segments[1].id = '训练' }],
    ['overlapping segment', (s: any) => { s.axis.segments[1].start = '2020-01-01T00:00:00'; s.axis.segments[1].end = '2020-01-01T01:40:00' }],
    ['out of order role', (s: any) => { s.axis.segments[2].role = 'train' }],
    ['source authentication', (s: any) => { s.source.authentication = 'AUTHENTICATED' }],
    ['source time basis', (s: any) => { s.source.time_basis = 'UTC' }],
  ] as const)('rejects summary %s before displaying partial content', async (_name, mutate) => {
    const s = summary(); mutate(s)
    const { root } = await mount(async () => response(s))
    expect(error(root)).toContain('格式不匹配')
    expect(root.querySelectorAll('[data-view-card],svg,tbody tr')).toHaveLength(0)
    expect(root.textContent).not.toContain('PRIVATE_TOKEN')
    expect(root.querySelector('[data-action="retry-summary"]')).not.toBeNull()
  })

  it.each([
    ['snapshot', (p: any) => { p.snapshot_sha256 = 'd'.repeat(64) }],
    ['different page', (p: any) => { p.page = 1 }],
    ['null scored value', (p: any) => { p.items[30].current13.score = null }],
    ['missing null', (p: any) => { delete p.items[0].current13.prediction }],
    ['unsaved reason', (p: any) => { p.items[0].reason = 'WARMUP' }],
    ['axis', (p: any) => { p.items[0].timestamp = '2020-01-02T00:00:00' }],
    ['wrong population', (p: any) => { p.items[30].scored = false }],
    ['wrong prediction', (p: any) => { p.items[30].current13.prediction = true }],
    ['false break', (p: any) => { p.items[30].break_before = false }],
    ['score boolean', (p: any) => { p.items[30].current13.score = false }],
    ['prediction number', (p: any) => { p.items[30].current13.prediction = 0 }],
    ['unscored zero', (p: any) => { p.items[0].h30_26.score = 0 }],
    ['wrong segment', (p: any) => { p.items[0].segment_id = '校准' }],
    ['wrong role', (p: any) => { p.items[0].role = 'calibration' }],
    ['missing index', (p: any) => { p.items[31].index = 32 }],
    ['unexpected reason on scored', (p: any) => { p.items[31].reason = 'NOT_SCORED_CAUSE_NOT_SAVED' }],
    ['short items', (p: any) => { p.items.pop() }],
    ['extra view field', (p: any) => { p.items[31].current13.label = 1 }],
    ['continuous unscored row', (p: any) => { p.items[32].break_before = false }],
  ] as const)('clears a bad series %s while retaining summary and offering explicit retry', async (_name, mutate) => {
    const p = page(); mutate(p)
    const { root } = await mount(async url => response(url.endsWith('summary') ? summary() : p))
    expect(error(root)).toContain('格式不匹配')
    expect(root.querySelectorAll('svg,tbody tr')).toHaveLength(0)
    expect(root.querySelectorAll('[data-view-card]')).toHaveLength(2)
    expect(root.querySelector('[data-action="retry-page"]')).not.toBeNull()
  })

  it('accepts 128 Unicode code points and renders markup characters only as text', async () => {
    const markup = '<img src=x onerror=PRIVATE_TOKEN>'
    const s = summary(), p = page(), id = markup + '😀'.repeat(128 - Array.from(markup).length)
    s.axis.segments[0].id = id; for (const row of p.items) row.segment_id = id
    expect(Array.from(id).length).toBe(128)
    const { root } = await mount(async url => response(url.endsWith('summary') ? s : p))
    expect(error(root)).toBe(''); expect(root.querySelectorAll('img,script,iframe')).toHaveLength(0)
    expect(root.textContent).toContain(id)
  })

  it('uses independent finite geometry, gaps, invalid lines and visible singletons', async () => {
    const { chartGeometry } = await api()
    const rows = [
      { index: 100, timestamp: '2020-01-01T00:00:00', segment_id: 'a', scored: true, break_before: false, current13: { score: 0, prediction: false } },
      { index: 101, timestamp: '2020-01-01T00:01:00', segment_id: 'a', scored: true, break_before: false, current13: { score: 0, prediction: true } },
      { index: 102, timestamp: '2020-01-01T00:03:00', segment_id: 'a', scored: true, break_before: true, current13: { score: Number.MAX_VALUE, prediction: false } },
      { index: 103, timestamp: '2020-01-01T00:04:00', segment_id: 'a', scored: false, break_before: true, current13: { score: null, prediction: null } },
      { index: 104, timestamp: '2020-01-02T00:00:00', segment_id: 'b', scored: true, break_before: true, current13: { score: -Number.MAX_VALUE, prediction: true } },
    ]
    const g = chartGeometry(rows, 'current13', 0)
    expect(g.runs.map((r: unknown[]) => r.length)).toEqual([2, 1, 1])
    expect(g.points.map((p: any) => p.alarm)).toEqual([false, true, false, true])
    for (const point of g.points) expect(Number.isFinite(point.x) && Number.isFinite(point.y)).toBe(true)
    expect(g.points[0].x).toBe(48); expect(g.points[3].x).toBe(608)
    const single = chartGeometry([rows[0]], 'current13', 0)
    expect(single.points).toHaveLength(1); expect(single.points[0].x).toBe(328)
    expect(Number.isFinite(single.points[0].y)).toBe(true)
    expect(chartGeometry([], 'current13', 0).points).toEqual([])
  })

  it.each(['summary', 'series'] as const)('accepts the exact %s byte limit despite a lying length header', async target => {
    const limit = target === 'summary' ? 16384 : 131072
    const payload = new Uint8Array(limit).fill(32); payload.set(bytes(target === 'summary' ? summary() : page()))
    const { root } = await mount(async url => url.includes(target) ? new Response(new ReadableStream({ start(c) {
      c.enqueue(payload.subarray(0, 19)); c.enqueue(payload.subarray(19)); c.close()
    } }), { headers: { 'Content-Type': 'application/json; charset=utf-8', 'Content-Length': '1' } }) : response(url.endsWith('summary') ? summary() : page()))
    expect(error(root)).toBe(''); expect(root.querySelectorAll('tbody tr')).toHaveLength(100)
  })

  it.each(['summary', 'series'] as const)('rejects %s limit+1 bytes and cancels the real stream', async target => {
    const limit = target === 'summary' ? 16384 : 131072, cancelled: string[] = []
    const payload = new Uint8Array(limit + 1).fill(32); payload.set(bytes(target === 'summary' ? summary() : page()))
    const { root } = await mount(async url => url.includes(target) ? new Response(new ReadableStream({ start(c) {
      c.enqueue(payload.subarray(0, limit)); c.enqueue(payload.subarray(limit))
    }, cancel() { cancelled.push(target) } }), { headers: { 'Content-Type': 'application/json', 'Content-Length': '1' } }) : response(summary()))
    expect(error(root)).toContain('超出读取上限'); expect(cancelled).toEqual([target])
    expect(root.querySelectorAll('svg,tbody tr')).toHaveLength(0)
    expect(root.querySelectorAll('[data-view-card]')).toHaveLength(target === 'summary' ? 0 : 2)
  })

  it.each(['utf8', 'media', 'missing media', 'http', 'nonbyte', 'missing stream', 'network'] as const)('safely rejects %s without fallback reads or external error content', async kind => {
    const { root } = await mount(async () => {
      if (kind === 'network') throw Error('PRIVATE_TOKEN')
      if (kind === 'utf8') return new Response(new Uint8Array([255]), { headers: { 'Content-Type': 'application/json' } })
      if (kind === 'media') return response(summary(), { 'Content-Type': 'text/html' })
      if (kind === 'missing media') return new Response(bytes(summary()))
      if (kind === 'http') return new Response('PRIVATE_TOKEN', { status: 500 })
      return { status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), text() { throw Error('unbounded fallback') },
        json() { throw Error('unbounded fallback') }, body: kind === 'missing stream' ? null : {
          getReader: () => ({ read: async () => ({ done: false, value: 'PRIVATE_TOKEN' }), cancel() {}, releaseLock() {} }),
        } }
    })
    expect(error(root)).toMatch(/格式不匹配|读取失败/); expect(root.textContent).not.toContain('PRIVATE_TOKEN')
    expect(root.querySelectorAll('[data-view-card],svg,tbody tr')).toHaveLength(0)
  })

  it.each(['resolve', 'reject'] as const)('ignores an obsolete page fetch %s and preserves the new page', async outcome => {
    const pending = deferred<unknown>(), signals: AbortSignal[] = []
    const { root } = await mount(async (url, init) => {
      if (url.endsWith('page=1')) { signals.push(init.signal!); return pending.promise }
      return response(url.endsWith('summary') ? summary() : page(0))
    })
    click(root, 'next'); await flush(); expect(root.querySelectorAll('svg,tbody tr')).toHaveLength(0)
    click(root, 'previous'); await flush()
    expect(signals[0]?.aborted).toBe(true)
    const snapshot = root.textContent
    if (outcome === 'resolve') pending.resolve(response(page(1))); else pending.reject(Error('PRIVATE_TOKEN'))
    await flush(); expect(root.textContent).toBe(snapshot)
    expect(root.querySelector('tbody tr')?.getAttribute('data-index')).toBe('0')
  })

  it.each(['resolve', 'reject'] as const)('cancels a noncooperative obsolete body and drops late %s/finally', async outcome => {
    const pending = deferred<{ done: boolean, value?: Uint8Array }>(), cancelled: number[] = []
    const { root } = await mount(async url => {
      if (url.endsWith('page=1')) return { status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), body: {
        getReader: () => ({ read: () => pending.promise, cancel() { cancelled.push(1) }, releaseLock() {} }),
      } }
      return response(url.endsWith('summary') ? summary() : page(0))
    })
    click(root, 'next'); await flush(); click(root, 'previous'); await flush()
    expect(cancelled).toEqual([1]); const snapshot = root.textContent
    if (outcome === 'resolve') pending.resolve({ done: false, value: bytes(page(1)) }); else pending.reject(Error('PRIVATE_TOKEN'))
    await flush(); expect(root.textContent).toBe(snapshot); expect(error(root)).toBe('')
  })

  it('keeps one total deadline across fetch and body and allows a manual summary retry', async () => {
    await api(); vi.useFakeTimers()
    const fetched = deferred<unknown>(), body = deferred<{ done: boolean }>(), cancels: number[] = []
    let attempt = 0, signal: AbortSignal | undefined
    const { root } = await mount(async (url, init) => {
      if (++attempt === 1) { signal = init.signal!; return fetched.promise }
      return response(url.endsWith('summary') ? summary() : page())
    })
    await vi.advanceTimersByTimeAsync(9500)
    fetched.resolve({ status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), body: {
      getReader: () => ({ read: () => body.promise, cancel() { cancels.push(1) }, releaseLock() {} }),
    } }); await flush(); await vi.advanceTimersByTimeAsync(500)
    expect(error(root)).toContain('读取超时'); expect(signal?.aborted).toBe(true); expect(cancels).toEqual([1])
    expect(vi.getTimerCount()).toBe(0)
    click(root, 'retry-summary'); await flush(); expect(root.querySelectorAll('tbody tr')).toHaveLength(100)
    const snapshot = root.textContent; body.resolve({ done: true }); await flush(); expect(root.textContent).toBe(snapshot)
  })

  it('expires an empty-chunk loop with the monotonic clock before a timer can run', async () => {
    let now = 0, readCount = 0, cancelled = false
    const { root } = await mount(async () => ({ status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), body: {
      getReader: () => ({ read: async () => { readCount++; now += 5000; return { done: false, value: new Uint8Array(0) } },
        cancel() { cancelled = true }, releaseLock() {} }),
    } }), { now: () => now })
    expect(error(root)).toContain('读取超时'); expect(readCount).toBe(2); expect(cancelled).toBe(true)
  })

  it.each(['destroy', 'pagehide'] as const)('disposes pending work on %s and never writes a late response', async action => {
    const pending = deferred<unknown>(); let signal: AbortSignal | undefined
    const { root, handle } = await mount(async (_url, init) => { signal = init.signal!; return pending.promise })
    if (action === 'destroy') handle.destroy(); else window.dispatchEvent(new Event('pagehide'))
    const snapshot = root.textContent; expect(signal?.aborted).toBe(true)
    pending.resolve(response(summary())); await flush(); expect(root.textContent).toBe(snapshot)
    handle.destroy()
  })

  it('deduplicates active mounts, removes listeners on destroy, and remounts a disposed root', async () => {
    const { root, handle } = await mount(), m = await api()
    expect(m.mountReleaseIFResultView(root)).toBe(handle)
    handle.destroy(); const snapshot = root.textContent; click(root, 'next'); await flush(); expect(root.textContent).toBe(snapshot)
    const second = m.mountReleaseIFResultView(root, { fetchImpl: async (url: string) => response(url.endsWith('summary') ? summary() : page()) })
    handles.push(second); expect(second).not.toBe(handle); await flush(); expect(root.querySelectorAll('tbody tr')).toHaveLength(100)
  })

  it('ends the busy state on a failed page, preserves summary and retries only on an explicit click', async () => {
    let pageAttempts = 0
    const { root } = await mount(async url => {
      if (url.endsWith('summary')) return response(summary())
      if (url.endsWith('page=1') && ++pageAttempts === 1) throw Error('PRIVATE_TOKEN')
      return response(page(Number(url.split('=')[1])))
    })
    click(root, 'next'); await flush()
    expect(error(root)).toContain('读取失败')
    expect(root.querySelector('[aria-busy="true"]')).toBeNull()
    expect(root.querySelectorAll('svg,tbody tr')).toHaveLength(0)
    expect(root.querySelectorAll('[data-view-card]')).toHaveLength(2)
    await flush(); expect(pageAttempts).toBe(1)
    click(root, 'retry-page'); await flush()
    expect(error(root)).toBe(''); expect(root.querySelector('tbody tr')?.getAttribute('data-index')).toBe('100')
    expect(pageAttempts).toBe(2)
  })

  it('preserves preprocessing-fit minutes that exceed all scored minutes', async () => {
    const s = summary(); s.views.current13.preprocessing_fit_count = 9; s.views.h30_26.preprocessing_fit_count = 9
    const { root } = await mount(async url => response(url.endsWith('summary') ? s : page()))
    expect(error(root)).toBe(''); expect(root.querySelectorAll('tbody tr')).toHaveLength(100)
    expect(root.querySelector('[data-view-card="current13"] [data-metric="preprocessing_fit_count"]')?.textContent).toBe('9')
    expect(root.querySelector('[data-view-card="h30_26"] [data-metric="preprocessing_fit_count"]')?.textContent).toBe('9')
  })

  it.each([70, 71])('bounds preprocessing-fit by the eligible train capacity at %i minutes', async count => {
    const s = summary(); s.views.current13.preprocessing_fit_count = count; s.views.h30_26.preprocessing_fit_count = count
    const { root } = await mount(async url => response(url.endsWith('summary') ? s : page()))
    if (count === 70) {
      expect(error(root)).toBe(''); expect(root.querySelectorAll('tbody tr')).toHaveLength(100)
      expect(root.querySelector('[data-view-card="current13"] [data-metric="preprocessing_fit_count"]')?.textContent).toBe('70')
    } else {
      expect(error(root)).toContain('格式不匹配'); expect(root.querySelectorAll('[data-view-card],svg,tbody tr')).toHaveLength(0)
    }
  })

  it.each([40, 41])('subtracts the first 30 minutes separately from each train segment for fit=%i', async count => {
    const s = summary()
    s.axis.segments[0].minute_count = 40; s.axis.segments[0].end = '2020-01-01T00:40:00'
    s.axis.segments.splice(1, 0, { ordinal: 1, id: '训练二', role: 'train', start: '2020-01-01T00:40:00', end: '2020-01-01T01:40:00', minute_count: 60, scored_count: 0 })
    s.axis.segments[2].ordinal = 2; s.axis.segments[3].ordinal = 3
    s.views.current13.preprocessing_fit_count = count; s.views.h30_26.preprocessing_fit_count = count
    const m = await api()
    if (count === 40) expect(m.validateSummary(s).views.current13.preprocessing_fit_count).toBe(40)
    else expect(() => m.validateSummary(s)).toThrow()
  })

  it.each(['resolve', 'reject'] as const)('automatically restores a persisted document and drops old fetch %s after working pagination', async outcome => {
    const root = document.createElement('main'); root.dataset.releaseIfResultView = ''; document.body.append(root)
    const old = deferred<unknown>(); let first = true
    vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
      const url = String(input)
      if (first) { first = false; return old.promise as Promise<Response> }
      return response(url.endsWith('summary') ? summary() : page(Number(url.split('=')[1])))
    })
    const source = Buffer.from(readFileSync(FILE)).toString('base64')
    const auto = await import(/* @vite-ignore */ `data:text/javascript;base64,${source}#bfcache-${outcome}`)
    const original = auto.mountReleaseIFResultView(root); handles.push(original); await flush()
    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }))
    window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })); await flush()
    try {
      expect(root.querySelectorAll('tbody tr')).toHaveLength(100)
      original.destroy()
      window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }))
      window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })); await flush()
      click(root, 'next'); await flush()
      expect(root.querySelector('tbody tr')?.getAttribute('data-index')).toBe('100')
      const snapshot = root.textContent
      if (outcome === 'resolve') old.resolve(response(summary())); else old.reject(Error('PRIVATE_TOKEN'))
      await flush(); expect(root.textContent).toBe(snapshot); expect(error(root)).toBe('')
      const restored = auto.mountReleaseIFResultView(root); restored.destroy()
      window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })); await flush()
      expect(root.textContent).toBe(snapshot)
    } finally {
      window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: false }))
    }
  })

  it.each(['before-hide', 'after-hide'] as const)('never revives an explicitly disposed automatic viewer destroyed %s', async timing => {
    const root = document.createElement('main'); root.dataset.releaseIfResultView = ''; document.body.append(root)
    const added = vi.spyOn(window, 'addEventListener'), removed = vi.spyOn(window, 'removeEventListener')
    const calls: string[] = []
    vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
      const url = String(input); calls.push(url)
      return response(url.endsWith('summary') ? summary() : page(Number(url.split('=')[1])))
    })
    const source = Buffer.from(readFileSync(FILE)).toString('base64')
    const auto = await import(/* @vite-ignore */ `data:text/javascript;base64,${source}#disposed-${timing}`)
    await flush(); expect(root.querySelectorAll('tbody tr')).toHaveLength(100)
    const handle = auto.mountReleaseIFResultView(root); handles.push(handle)
    const snapshot = root.textContent, requestCount = calls.length
    try {
      if (timing === 'before-hide') handle.destroy()
      window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true }))
      if (timing === 'after-hide') handle.destroy()
      window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })); await flush()
      window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })); await flush()
      for (const type of ['pagehide', 'pageshow']) {
        const registered = added.mock.calls.filter(([event]) => event === type)
        expect(registered.length).toBeGreaterThan(0)
        for (const [, listener, options] of registered) {
          const capture = typeof options === 'boolean' ? options : !!options?.capture
          expect(removed.mock.calls.some(([event, callback, removal]) => event === type && callback === listener
            && (typeof removal === 'boolean' ? removal : !!removal?.capture) === capture)).toBe(true)
        }
      }
      expect(calls).toHaveLength(requestCount); expect(root.textContent).toBe(snapshot)
    } finally {
      window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: false }))
    }
  })

  it('rejects a UTF-8 BOM instead of silently dropping a non-protocol prefix', async () => {
    const payload = bytes(summary()), bom = new Uint8Array(payload.length + 3)
    bom.set([239, 187, 191]); bom.set(payload, 3)
    const { root } = await mount(async () => new Response(bom, { headers: { 'Content-Type': 'application/json' } }))
    expect(error(root)).toContain('格式不匹配'); expect(root.querySelectorAll('[data-view-card]')).toHaveLength(0)
  })

  it('accepts real >64KiB Unicode pages, finite extremes, and a 10000-minute final page', async () => {
    const s = summary(), p = page()
    s.axis.minute_count = 10000; s.axis.unscored_count = 9994; s.axis.page_count = 100
    s.axis.segments[2].minute_count = 9800; s.axis.segments[2].end = '2020-01-09T19:20:00'
    for (const [index, segment] of s.axis.segments.entries()) segment.id = ['😀', '🚦', '🌊'][index]!.repeat(128)
    p.total = 10000; for (const row of p.items) row.segment_id = s.axis.segments[0].id
    p.items[30].current13.score = -Number.MAX_VALUE; p.items[31].current13.score = Number.MAX_VALUE
    p.items[30].h30_26.score = -Number.MAX_VALUE; p.items[31].h30_26.score = Number.MAX_VALUE
    expect(bytes(p).byteLength).toBeGreaterThan(65536); expect(bytes(p).byteLength).toBeLessThanOrEqual(131072)
    const { root } = await mount(async url => response(url.endsWith('summary') ? s : p))
    expect(error(root)).toBe(''); expect(root.querySelectorAll('tbody tr')).toHaveLength(100)
    for (const mark of root.querySelectorAll('circle,path')) expect(mark.outerHTML).not.toMatch(/NaN|Infinity/)
    const last = { version: 1, profile_id: Q, scope: SCOPE, snapshot_sha256: SNAPSHOT, page: 99, page_size: 100, total: 10000, returned: 100,
      items: Array.from({ length: 100 }, (_, i) => ({ index: 9900 + i,
        timestamp: new Date(Date.UTC(2020, 0, 9, 17, 40 + i)).toISOString().slice(0, 19),
        segment_id: s.axis.segments[2].id, role: 'test', break_before: true, scored: false,
        current13: { score: null, prediction: null }, h30_26: { score: null, prediction: null }, reason: 'NOT_SCORED_CAUSE_NOT_SAVED' })) }
    const m = await api(); expect(m.validateSeries(last, m.validateSummary(s), 99).items[99].index).toBe(9999)
  })

  it.each(['resolve', 'reject'] as const)('ignores a timed-out noncooperative summary fetch %s after an explicit retry', async outcome => {
    await api(); vi.useFakeTimers(); const pending = deferred<unknown>(); let first = true
    const { root } = await mount(async url => {
      if (first) { first = false; return pending.promise }
      return response(url.endsWith('summary') ? summary() : page())
    })
    await vi.advanceTimersByTimeAsync(10000); expect(error(root)).toContain('读取超时')
    click(root, 'retry-summary'); await flush(); expect(root.querySelectorAll('tbody tr')).toHaveLength(100)
    const snapshot = root.textContent
    if (outcome === 'resolve') pending.resolve(response(summary())); else pending.reject(Error('PRIVATE_TOKEN'))
    await flush(); expect(root.textContent).toBe(snapshot); expect(vi.getTimerCount()).toBe(0)
  })

  it('gives the page its own deadline after summary and retains the full summary on page timeout', async () => {
    await api(); vi.useFakeTimers(); const fetchSummary = deferred<unknown>(), fetchPage = deferred<unknown>()
    const { root } = await mount(async url => url.endsWith('summary') ? fetchSummary.promise : fetchPage.promise)
    await vi.advanceTimersByTimeAsync(9500); fetchSummary.resolve(response(summary())); await flush()
    await vi.advanceTimersByTimeAsync(500); expect(error(root)).toBe('')
    await vi.advanceTimersByTimeAsync(9500); expect(error(root)).toContain('读取超时')
    expect(root.querySelectorAll('[data-view-card]')).toHaveLength(2); expect(root.querySelectorAll('svg,tbody tr')).toHaveLength(0)
    expect(root.querySelector('[data-action="retry-page"]')).not.toBeNull(); expect(vi.getTimerCount()).toBe(0)
    const snapshot = root.textContent; fetchPage.resolve(response(page())); await flush(); expect(root.textContent).toBe(snapshot)
  })

  it.each(['destroy', 'pagehide'] as const)('releases a pending body on %s and ignores both late body outcomes', async action => {
    await api(); vi.useFakeTimers(); const pending = deferred<{ done: boolean, value?: Uint8Array }>()
    let cancelled = 0, released = 0
    const { root, handle } = await mount(async () => ({ status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), body: {
      getReader: () => ({ read: () => pending.promise, cancel() { cancelled++ }, releaseLock() { released++ } }),
    } }))
    if (action === 'destroy') handle.destroy(); else window.dispatchEvent(new Event('pagehide'))
    await flush(); const snapshot = root.textContent
    expect(cancelled).toBe(1); expect(released).toBe(1); expect(vi.getTimerCount()).toBe(0)
    pending.reject(Error('PRIVATE_TOKEN')); await flush(); expect(root.textContent).toBe(snapshot)
  })

  it.each([2, 3])('requires the extra scored predecessor implied by a false page-start break with segment scored_count=%i', async scoredCount => {
    const s = summary(); s.axis.minute_count = 401; s.axis.scored_count = scoredCount + 4; s.axis.unscored_count = 397 - scoredCount; s.axis.page_count = 5
    s.axis.segments[0].minute_count = 200; s.axis.segments[0].end = '2020-01-01T03:20:00'
    s.axis.segments[0].scored_count = scoredCount; s.axis.segments[1].minute_count = 200; s.axis.segments[1].end = '2020-01-02T03:20:00'
    const p = page(1); p.total = 401
    for (const [i, row] of p.items.entries()) {
      row.timestamp = new Date(Date.UTC(2020, 0, 1, 1, 40 + i)).toISOString().slice(0, 19)
      row.segment_id = '训练'; row.role = 'train'; row.scored = i === 0 || i === 1
      row.break_before = i >= 2; row.reason = row.scored ? null : 'NOT_SCORED_CAUSE_NOT_SAVED'
      row.current13 = { score: row.scored ? 0 : null, prediction: row.scored ? false : null }
      row.h30_26 = { score: row.scored ? 0 : null, prediction: row.scored ? false : null }
    }
    const m = await api()
    if (scoredCount === 2) {
      expect(() => m.validateSeries(p, m.validateSummary(s), 1)).toThrow(); return
    }
    const valid = m.validateSeries(p, m.validateSummary(s), 1)
    const geometry = m.chartGeometry(valid.items, 'current13', 1)
    expect(geometry.runs.map((run: any[]) => run.length)).toEqual([2]); expect(geometry.points[0].x).toBe(48)
  })

  it('rejects page-start continuity that requires an ineligible segment minute 29 to be scored', async () => {
    const s = summary(); s.axis.minute_count = 401; s.axis.scored_count = 8; s.axis.unscored_count = 393; s.axis.page_count = 5
    s.axis.segments[0].minute_count = 70; s.axis.segments[0].end = '2020-01-01T01:10:00'
    s.axis.segments.splice(1, 0, { ordinal: 1, id: '训练二', role: 'train', start: '2020-01-01T02:00:00', end: '2020-01-01T04:10:00', minute_count: 130, scored_count: 2 })
    s.axis.segments[2].ordinal = 2; s.axis.segments[2].minute_count = 200; s.axis.segments[2].end = '2020-01-02T03:20:00'; s.axis.segments[3].ordinal = 3
    const p = page(1); p.total = 401
    for (const [i, row] of p.items.entries()) {
      row.timestamp = new Date(Date.UTC(2020, 0, 1, 2, 30 + i)).toISOString().slice(0, 19)
      row.segment_id = '训练二'; row.role = 'train'; row.scored = i === 0 || i === 1
      row.break_before = i >= 2; row.reason = row.scored ? null : 'NOT_SCORED_CAUSE_NOT_SAVED'
      row.current13 = { score: row.scored ? 0 : null, prediction: row.scored ? false : null }
      row.h30_26 = { score: row.scored ? 0 : null, prediction: row.scored ? false : null }
    }
    const m = await api(); expect(() => m.validateSeries(p, m.validateSummary(s), 1)).toThrow()
    p.items[0].break_before = true
    expect(m.validateSeries(p, m.validateSummary(s), 1).items[0].index).toBe(100)
  })

  it('keeps local HTML resources and accessible table/page controls', async () => {
    const html = new DOMParser().parseFromString(readFileSync(resolve(DIR, 'results.html'), 'utf8'), 'text/html')
    expect(html.querySelector('html')?.lang).toBe('zh-CN')
    expect(html.querySelector('meta[name="viewport"]')).not.toBeNull()
    expect(html.querySelector('script')?.getAttribute('src')).toBe('/release/results/results.mjs')
    expect(html.querySelector('link')?.getAttribute('href')).toBe('/release/results/results.css')
    expect(html.querySelectorAll('script')).toHaveLength(1)
    expect(html.querySelector('script')?.textContent).toBe('')
    const { root } = await mount()
    expect(root.querySelector('table caption')?.textContent).toContain('保存')
    expect(root.querySelectorAll('th[scope="col"]')).toHaveLength(10)
    expect(root.querySelector('[data-action="next"]')?.tagName).toBe('BUTTON')
    expect(root.querySelector('[role="region"]')?.getAttribute('aria-label')).toContain('横向滚动')
    for (const file of ['results.html', 'results.mjs', 'results.css']) expect(readFileSync(resolve(DIR, file)).byteLength).toBeLessThanOrEqual(65536)
  })
})
