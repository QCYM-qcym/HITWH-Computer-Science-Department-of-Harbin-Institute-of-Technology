import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createHash, webcrypto } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { delimiter, dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../../../')
const ASSETS = resolve(ROOT, 'src/backend/traffic_api/release_if_learned_static')
const OLD = resolve(ROOT, 'src/backend/traffic_api/release_if_static/results.mjs')
const FILE = resolve(ASSETS, 'learned.mjs')
const VIEWS = ['current13', 'h30_26']
const HASH = 'a'.repeat(64)
const BASE = ['completed_source_record_count', 'fwd_packet_sum', 'bwd_packet_sum', 'fwd_source_length_sum',
  'bwd_source_length_sum', 'tcp_source_record_count', 'udp_source_record_count', 'known_other_source_protocol_record_count',
  'unresolved_source_protocol_record_count', 'duration_max_s', 'duration_median_s', 'duration_p95_s', 'no_backward_packet_source_record_count']
const id = (profile: string, hash = HASH) => ({ profile_id: profile, context_sha256: hash, manifest_sha256: hash, manifest_byte_count: 1234 })
const config = (width: number, m = 2) => ({ input_width: width, n_estimators: 16, max_samples: m, max_features: 1,
  bootstrap: false, contamination: 'auto', random_state: 42, n_jobs: 1 })
const clone = (value: any) => JSON.parse(JSON.stringify(value))
const utf8 = (value: string) => new TextEncoder().encode(value)
const hash = (value: string | Uint8Array) => createHash('sha256').update(value).digest('hex')
// Independent closed-schema oracle, not the product canonicalizer.
function canonical(value: any, path: string[] = []): string {
  if (Array.isArray(value)) return '[' + value.map((x, i) => canonical(x, [...path, String(i)])).join(',') + ']'
  if (value !== null && typeof value === 'object') return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonical(value[k], [...path, k])).join(',') + '}'
  const view = path[1]
  if (path.length === 5 && path[0] === 'views' && typeof view === 'string' && VIEWS.includes(view) && path.slice(2).join('.') === 'declarations.model_configuration.max_features') return '1.0'
  return JSON.stringify(value)
}
function oldSummary(): any {
  const value = { version: 1, profile_id: 'c17-release-iforest-view-v1', scope: 'SAVED_RESULT_INTERNAL_CONSISTENCY_ONLY', snapshot_sha256: '',
    source: { schema_id: 'c17-release-91-v1', authentication: 'NOT_AUTHENTICATED', time_basis: 'SOURCE_WALL_CLOCK_COMPLETION_PROXY', policy_status: 'AUDIT_ONLY', audit_fit_policy: 'P_U' },
    input_references: { raw: id('c17-release-minute-package-v1'), prepared: id('c17-release-prepared-input-package-v1'), configuration_sha256: HASH },
    result_references: { current13: id('c17-release-iforest-result-package-v1', 'b'.repeat(64)), h30_26: id('c17-release-iforest-result-package-v1', 'c'.repeat(64)) },
    axis: { minute_count: 300, scored_count: 6, unscored_count: 294, page_size: 100, page_count: 3,
      segments: [
        { ordinal: 0, id: '训练', role: 'train', start: '2020-01-01T00:00:00', end: '2020-01-01T01:40:00', minute_count: 100, scored_count: 2 },
        { ordinal: 1, id: '校准', role: 'calibration', start: '2020-01-02T00:00:00', end: '2020-01-02T01:40:00', minute_count: 100, scored_count: 4 },
        { ordinal: 2, id: '测试', role: 'test', start: '2020-01-03T00:00:00', end: '2020-01-03T01:40:00', minute_count: 100, scored_count: 0 },
      ] },
    views: { current13: { configuration: config(13), threshold: 1, training_count: 2, calibration_count: 4, preprocessing_fit_count: 3, equal_threshold_count: 3, above_threshold_count: 0 },
      h30_26: { configuration: config(26), threshold: 2, training_count: 2, calibration_count: 4, preprocessing_fit_count: 3, equal_threshold_count: 3, above_threshold_count: 0 } },
    checks: { internal_consistency: 'MATCHED', saved_score_q99: 'MATCHED', cross_view_binding: 'MATCHED', input_pair_binding: 'NOT_PERFORMED', source_authentication: 'NOT_AUTHENTICATED', model_execution: 'NOT_AUTHENTICATED' } }
  value.snapshot_sha256 = hash(canonical({ ...value.result_references, profile_id: value.profile_id }) + '\n')
  return value
}
function learned(view: string, old: any): any {
  return { version: 1, profile_id: 'c17-release-iforest-learned-summary-v1', scope: 'SAVED_LEARNED_INTERNAL_CONSISTENCY_ONLY',
    learned_identity: id('c17-release-iforest-learned-package-v1', (view === 'current13' ? 'd' : 'e').repeat(64)), view,
    input_references: { raw: clone(old.input_references.raw), prepared: clone(old.input_references.prepared) }, result_reference: clone(old.result_references[view]),
    declarations: { configuration_sha256: HASH, population_sha256: 'f'.repeat(64), input_rules_id: 'c17-release-log1p-mad-input-rules-v1',
      feature_columns: BASE.map(n => 'current:' + n).concat(view === 'current13' ? [] : BASE.map(n => 'residual_h30:' + n)),
      model_configuration: config(view === 'current13' ? 13 : 26), fit_runtime_id: 'python314-numpy254-sklearn191-joblib160-serial-wm1024-v1' },
    counts: { total: 300, training: 2, calibration: 4, preprocessing_fit: 3, trees: 16, nodes: 16 },
    checks: { byte_integrity: 'MATCHED', structure: 'MATCHED', numerical_replay: 'NOT_RUN', input_pair_binding: 'NOT_PERFORMED', result_binding: 'NOT_PERFORMED', source_authentication: 'NOT_AUTHENTICATED', model_origin: 'NOT_AUTHENTICATED' } }
}
function seal(value: any): any { const copy = { ...value }; delete copy.snapshot_sha256; value.snapshot_sha256 = hash(canonical(copy) + '\n'); return value }
function fixture(): { value: any; old: any } {
  const old = oldSummary(), a = learned('current13', old), b = learned('h30_26', old)
  return { old, value: seal({ version: 1, profile_id: 'c17-release-iforest-learned-view-v1', scope: 'REGISTERED_SAVED_LEARNED_TUPLE_INSPECTION_ONLY',
    snapshot_sha256: '', result_snapshot_sha256: old.snapshot_sha256,
    input_references: { raw: clone(old.input_references.raw), prepared: clone(old.input_references.prepared) }, result_references: clone(old.result_references),
    learned_references: { current13: clone(a.learned_identity), h30_26: clone(b.learned_identity) },
    populations: { total: 300, common: 6, unscored: 294, test_total: 100, test_common: 0, training: 2, calibration: 4, preprocessing_fit: 3 },
    views: { current13: a, h30_26: b }, registration_checks: { input_pair_binding: 'MATCHED', result_pair_binding: 'MATCHED', learned_declarations_binding: 'MATCHED' },
    replay: null, limits: { metadata_bytes: 65536, source_axis_minutes: 10000, result_page_size: 100, result_page_bytes: 131072 } }) }
}
let uriCounter = 0, cached: Promise<any> | undefined
function oldURI() { return 'data:text/javascript;base64,' + Buffer.from(readFileSync(OLD, 'utf8') + '\n// fresh old identity ' + ++uriCounter).toString('base64') }
async function api(fresh = false): Promise<any> {
  expect(existsSync(FILE), 'new learned consumer module must exist').toBe(true)
  const load = () => {
    const source = readFileSync(FILE, 'utf8'), needle = "'/release/results/results.mjs'"
    expect(source.split(needle)).toHaveLength(2)
    return import(/* @vite-ignore */ 'data:text/javascript;base64,' + Buffer.from(source.replace(needle, JSON.stringify(oldURI())) + '\n// fresh learned ' + ++uriCounter).toString('base64'))
  }
  return fresh ? load() : cached ??= load()
}
const response = (value: any, options: ResponseInit = {}) => new Response(utf8(JSON.stringify(value) + '\n'), { headers: { 'Content-Type': 'application/json' }, ...options })
function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void; const promise = new Promise<T>((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
let digests: Promise<ArrayBuffer>[] = []
const handles: Array<{ destroy(): void }> = []
beforeEach(() => { digests = []; vi.stubGlobal('crypto', { subtle: { digest: (...args: Parameters<typeof webcrypto.subtle.digest>) => { const p = webcrypto.subtle.digest(...args); digests.push(p); return p } } }) })
afterEach(() => { for (const h of handles.splice(0)) h.destroy(); document.body.replaceChildren(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
async function flush(crypto = true) { for (let i = 0; i < 120; i++) await Promise.resolve(); if (crypto) { let i = 0; while (i < digests.length) await digests[i++] } for (let i = 0; i < 120; i++) await Promise.resolve() }
async function mount(fetchImpl?: any, options: any = {}) {
  const m = await api(), { value, old } = fixture(), root = document.createElement('main'); document.body.append(root)
  const calls: string[] = []
  const fetcher = fetchImpl ?? (async (url: string, init: RequestInit) => { calls.push(url); expect(init.cache).toBe('no-store'); return response(url.startsWith('/release-if-learned') ? value : old) })
  const h = m.mountReleaseIFLearnedView(root, { fetchImpl: fetcher, ...options }); handles.push(h); await flush(options.noCrypto !== true); return { m, root, h, calls }
}
function retry(root: HTMLElement) { (root.querySelector('[data-action="retry"]') as HTMLButtonElement).click() }

describe('learned view independent consumer', () => {
  it('exports the closed consumer and binds full identities with a long unscored test population', async () => {
    const m = await api(), { value, old } = fixture(), frozen = JSON.stringify({ value, old })
    for (const name of ['validateLearnedSummary', 'validateLearnedView', 'canonicalLearnedViewBytes', 'verifyLearnedView', 'mountReleaseIFLearnedView']) expect(m[name]).toBeTypeOf('function')
    expect(m.validateLearnedSummary(value.views.current13, 'current13')).toBe(value.views.current13)
    expect(m.validateLearnedView(value, old)).toBe(value)
    expect(await m.verifyLearnedView(value, old)).toBe(value)
    expect(value.populations.test_total).toBeGreaterThan(value.populations.common)
    expect(JSON.stringify({ value, old })).toBe(frozen)
  })
  it('emits exactly the two Python1.0 tokens with sorted bytes and LF', async () => {
    const m = await api(), { value } = fixture(), pre = { ...value }; delete pre.snapshot_sha256
    const actual = m.canonicalLearnedViewBytes(value)
    expect(new TextDecoder().decode(actual)).toBe(canonical(pre) + '\n')
    const text = new TextDecoder().decode(actual); expect(text.match(/"max_features":1\.0/g)).toHaveLength(2)
    const negative = text.replaceAll('"max_features":1.0', '"max_features":1')
    expect(hash(actual)).toBe(value.snapshot_sha256); expect(hash(negative)).not.toBe(value.snapshot_sha256)
  })
  it('rejects a one-sided population digest despite a self-consistent outer rehash', async () => {
    const m = await api(), { value, old } = fixture(); value.views.h30_26.declarations.population_sha256 = '1'.repeat(64); seal(value)
    expect(() => m.validateLearnedView(value, old)).toThrowError(expect.objectContaining({ code: 'IDENTITY_MISMATCH' }))
  })
  it.each([1, 2, 32])('enforces the even tree aggregate at m%s without changing the shared projection', async msize => {
    const m = await api(), s = fixture().value.views.current13
    s.counts.training = s.counts.preprocessing_fit = msize; s.declarations.model_configuration.max_samples = msize
    for (const nodes of [16, 16 * (2 * msize - 1)]) { s.counts.nodes = nodes; expect(m.validateLearnedSummary(s, 'current13')).toBe(s) }
    for (const nodes of [15, 17, 16 * (2 * msize - 1) + 2]) { s.counts.nodes = nodes; expect(() => m.validateLearnedSummary(s, 'current13')).toThrow() }
  })
  it.each([
    (v: any) => { v.extra = true }, (v: any) => { delete v.replay }, (v: any) => { v.replay = false },
    (v: any) => { v.populations.total = true }, (v: any) => { v.populations.test_common = 7 },
    (v: any) => { v.views.current13.checks.numerical_replay = 'MATCHED' },
    (v: any) => { v.views.current13.declarations.feature_columns.reverse() },
    (v: any) => { v.views.current13.declarations.model_configuration.max_features = 1.1 },
    (v: any) => { v.learned_references.current13.manifest_byte_count = 8193 },
    (v: any) => { v.populations.test_common = -0 }, (v: any) => { v.limits.metadata_bytes++ },
    (v: any) => { v.views.current13.counts.nodes = 1008 },
  ])('rejects malformed closed data rather than rendering a default', async change => {
    const m = await api(), { value, old } = fixture(); change(value); expect(() => m.validateLearnedView(value, old)).toThrow()
  })
  it.each(['raw', 'prepared'])('compares every %s reference field across both summaries', async field => {
    const m = await api(), { value, old } = fixture(); old.input_references[field].manifest_byte_count++
    expect(() => m.validateLearnedView(value, old)).toThrowError(expect.objectContaining({ code: 'IDENTITY_MISMATCH' }))
  })
  it('verifies the old digest as well as the entire new envelope', async () => {
    const m = await api(), { value, old } = fixture(); old.snapshot_sha256 = value.result_snapshot_sha256 = '0'.repeat(64); seal(value)
    await expect(m.verifyLearnedView(value, old)).rejects.toMatchObject({ code: 'SNAPSHOT_MISMATCH' })
  })
  it('renders only both-summary bound Chinese declarations, real zero and a local result link', async () => {
    const { root, calls } = await mount()
    expect(calls.sort()).toEqual(['/release-if-learned/v1/summary', '/release-if/v1/summary'].sort())
    expect(root.dataset.state).toBe('ready'); expect(root.getAttribute('aria-busy')).toBe('false')
    expect(root.querySelectorAll('[data-view-card]')).toHaveLength(2)
    expect(root.querySelector('a')?.getAttribute('href')).toBe('/release/results')
    for (const text of ['学习状态包检查', 'NOT_RUN', 'NOT_AUTHENTICATED', 'NOT_PERFORMED', '全轴', '测试', '100', 'false', '0', '仅核对', '本页未执行显式数值复算']) expect(root.textContent).toContain(text)
    expect(root.textContent).not.toMatch(/FAILED_OBSERVER|R2.*PASS|准确率|F1|AUROC|C:\\Users/)
    expect(root.querySelector('[data-release-if-result-view]')).toBeNull()
  })
  it.each(['status', 'mime', 'BOM', 'UTF8', 'oversize', 'shape'])('clears partial success on %s failure and offers explicit retry', async kind => {
    const f = fixture(); let failed = true
    const { root } = await mount(async (url: string) => {
      if (!url.startsWith('/release-if-learned') || !failed) return response(url.startsWith('/release-if-learned') ? f.value : f.old)
      if (kind === 'status') return response({}, { status: 500 })
      if (kind === 'mime') return response(f.value, { headers: { 'Content-Type': 'text/html' } })
      if (kind === 'BOM') return new Response(new Uint8Array([239, 187, 191, ...utf8(JSON.stringify(f.value))]), { headers: { 'Content-Type': 'application/json' } })
      if (kind === 'UTF8') return new Response(new Uint8Array([255]), { headers: { 'Content-Type': 'application/json' } })
      if (kind === 'oversize') return new Response(new Uint8Array(65537), { headers: { 'Content-Type': 'application/json', 'Content-Length': '1' } })
      return response({})
    })
    expect(root.dataset.state).toBe('error'); expect(root.querySelectorAll('[data-view-card],a')).toHaveLength(0)
    expect(root.querySelector('[role="alert"]')?.textContent).toBeTruthy(); failed = false; retry(root); await flush(); expect(root.dataset.state).toBe('ready')
  })
  it('cancels a late noncooperating sibling body after aggregate failure', async () => {
    const late = deferred<any>(), cancel = vi.fn(async () => {}), getReader = vi.fn()
    const { root } = await mount((url: string) => url.startsWith('/release-if-learned') ? Promise.resolve(response({}, { status: 500 })) : late.promise)
    expect(root.dataset.state).toBe('error'); late.resolve({ status: 200, body: { cancel, getReader } }); await flush()
    expect(cancel).toHaveBeenCalledTimes(1); expect(getReader).not.toHaveBeenCalled(); expect(root.dataset.state).toBe('error')
  })
  it('handles late sibling rejection without stale rendering', async () => {
    const late = deferred<any>(), { root } = await mount((url: string) => url.startsWith('/release-if-learned') ? Promise.resolve(response({}, { status: 500 })) : late.promise)
    late.reject(new Error('private sentinel')); await flush(); expect(root.dataset.state).toBe('error'); expect(root.textContent).not.toContain('private sentinel')
  })
  it('never starts the second digest after timeout and retry while the first was pending', async () => {
    vi.useFakeTimers(); const pending = deferred<ArrayBuffer>(), calls: Uint8Array[] = []
    vi.stubGlobal('crypto', { subtle: { digest: (_algorithm: string, bytes: Uint8Array) => {
      calls.push(new Uint8Array(bytes)); if (calls.length === 1) return pending.promise
      const p = webcrypto.subtle.digest('SHA-256', new Uint8Array(bytes)); digests.push(p); return p
    } } })
    const { root } = await mount(undefined, { now: () => Date.now(), noCrypto: true }); expect(calls).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(10000); expect(root.dataset.state).toBe('error')
    retry(root); await flush(); expect(root.dataset.state).toBe('ready'); expect(calls).toHaveLength(3)
    const firstCall = calls[0]; if (firstCall === undefined) throw new Error('first digest input missing')
    pending.resolve(await webcrypto.subtle.digest('SHA-256', new Uint8Array(firstCall))); await flush(); expect(calls).toHaveLength(3); expect(root.dataset.state).toBe('ready')
  })
  it('captures both verifier preimages synchronously before the first digest', async () => {
    const m = await api(), f = fixture(), first = deferred<ArrayBuffer>(), captured: Uint8Array[] = []
    vi.stubGlobal('crypto', { subtle: { digest: (_a: string, b: Uint8Array) => { captured.push(new Uint8Array(b)); return captured.length === 1 ? first.promise : webcrypto.subtle.digest('SHA-256', new Uint8Array(b)) } } })
    const promise = m.verifyLearnedView(f.value, f.old); expect(captured).toHaveLength(1)
    const firstInput = captured[0]; if (firstInput === undefined) throw new Error('captured digest input missing')
    first.resolve(await webcrypto.subtle.digest('SHA-256', new Uint8Array(firstInput))); expect(await promise).toBe(f.value)
    expect(new TextDecoder().decode(captured[1])).toBe(canonical({ ...f.old.result_references, profile_id: f.old.profile_id }) + '\n')
  })
  it('keeps one deadline through body reads and cancels owned readers', async () => {
    vi.useFakeTimers(); const f = fixture(), slow = deferred<ReadableStreamReadResult<Uint8Array>>(), cancel = vi.fn(async () => {})
    const { root } = await mount(async (url: string) => url.startsWith('/release-if-learned') ? response(f.value) : {
      status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), body: { getReader: () => ({ read: () => slow.promise, cancel, releaseLock() {} }) },
    }, { now: () => Date.now(), noCrypto: true })
    await vi.advanceTimersByTimeAsync(10000); expect(root.dataset.state).toBe('error'); expect(cancel).toHaveBeenCalledTimes(1)
    slow.resolve({ done: true, value: undefined }); await flush(); expect(root.dataset.state).toBe('error')
  })
  it('expires a zero-chunk loop with the shared monotonic clock', async () => {
    const f = fixture(); let clock = 0, reads = 0; const cancel = vi.fn(async () => {})
    const { root } = await mount(async (url: string) => url.startsWith('/release-if-learned') ? {
      status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), body: { getReader: () => ({
        read: async () => { reads++; clock += 2500; return { done: false, value: new Uint8Array() } }, cancel, releaseLock() {},
      }) },
    } : response(f.old), { now: () => clock })
    expect(root.dataset.state).toBe('error'); expect(reads).toBeLessThanOrEqual(4); expect(cancel).toHaveBeenCalled()
  })
  it('gates the atomic commit after reentrant destruction during detached rendering', async () => {
    const m = await api(), f = fixture(), root = document.createElement('main'); document.body.append(root)
    const h = m.mountReleaseIFLearnedView(root, { fetchImpl: async (url: string) => response(url.startsWith('/release-if-learned') ? f.value : f.old) }); handles.push(h)
    const real = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation(((tag: string, options?: ElementCreationOptions) => { if (tag === 'section') h.destroy(); return real(tag, options) }) as Document['createElement'])
    await flush(); expect(root.dataset.state).toBe('destroyed'); expect(root.querySelectorAll('[data-view-card],a')).toHaveLength(0)
  })
  it('deduplicates, disposes late bodies and supports a fresh explicit mount', async () => {
    const m = await api(), late = deferred<any>(), root = document.createElement('main'); document.body.append(root)
    const h = m.mountReleaseIFLearnedView(root, { fetchImpl: () => late.promise }); handles.push(h)
    expect(m.mountReleaseIFLearnedView(root, { fetchImpl: vi.fn() })).toBe(h)
    await flush(false); h.destroy(); h.destroy(); const cancel = vi.fn(async () => {}); late.resolve({ body: { cancel } }); await flush()
    expect(cancel).toHaveBeenCalled(); expect(root.dataset.state).toBe('destroyed')
    const f = fixture(), next = m.mountReleaseIFLearnedView(root, { fetchImpl: async (url: string) => response(url.startsWith('/release-if-learned') ? f.value : f.old) }); handles.push(next)
    await flush(); expect(next).not.toBe(h); expect(root.dataset.state).toBe('ready')
  })
  it('fails closed without SubtleCrypto', async () => {
    vi.stubGlobal('crypto', {}); const { root } = await mount(); expect(root.dataset.state).toBe('error'); expect(root.querySelector('a')).toBeNull()
  })
  it('imports a fresh old module with learned root present and no old side effects', async () => {
    const root = document.createElement('main'); root.dataset.releaseIfLearnedView = ''; document.body.append(root)
    const fetch = vi.fn(), events = vi.spyOn(window, 'addEventListener'); vi.stubGlobal('fetch', fetch)
    await import(/* @vite-ignore */ oldURI()); expect(fetch).not.toHaveBeenCalled(); expect(events).not.toHaveBeenCalled()
  })
  it('restarts BFcache ownership but never resurrects an explicitly destroyed root', async () => {
    const root = document.createElement('main'); root.dataset.releaseIfLearnedView = ''; document.body.append(root)
    const f = fixture(), fetch = vi.fn(async (url: string) => response(url.startsWith('/release-if-learned') ? f.value : f.old)); vi.stubGlobal('fetch', fetch)
    const m = await api(true); await flush(); const h = m.mountReleaseIFLearnedView(root); handles.push(h); expect(fetch).toHaveBeenCalledTimes(2)
    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true })); expect(root.dataset.state).toBe('destroyed')
    window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })); await flush(); expect(fetch).toHaveBeenCalledTimes(4)
    const next = m.mountReleaseIFLearnedView(root); handles.push(next); next.destroy()
    window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true })); window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })); await flush(); expect(fetch).toHaveBeenCalledTimes(4)
  })
  it('keeps local assets and usable narrow-screen styling', async () => {
    const html = readFileSync(resolve(ASSETS, 'learned.html'), 'utf8'), css = readFileSync(resolve(ASSETS, 'learned.css'), 'utf8')
    expect(html).toContain('data-release-if-learned-view'); expect(html).not.toContain('data-release-if-result-view')
    expect(html).toContain('/release/learned/learned.mjs'); expect(html).toContain('/release/learned/learned.css')
    expect(html).not.toMatch(/<style|style=|https?:\/\//); expect(css).toMatch(/overflow-wrap/); expect(css).toMatch(/focus-visible/)
  })
  it.each([
    ['learned', 65536, true], ['learned', 65537, false], ['old', 16384, true], ['old', 16385, false],
  ])('uses actual streamed %s byte boundary %s rather than Content-Length', async (target, length, valid) => {
    const f = fixture(), { root } = await mount(async (url: string) => {
      const isNew = url.startsWith('/release-if-learned'), selected = target === (isNew ? 'learned' : 'old'), body = isNew ? f.value : f.old
      if (!selected) return response(body)
      const data = new Uint8Array(Number(length)).fill(32); data.set(utf8(JSON.stringify(body) + '\n'))
      return new Response(data, { headers: { 'Content-Type': 'application/json', 'Content-Length': '1' } })
    })
    expect(root.dataset.state).toBe(valid ? 'ready' : 'error')
  })
  it.each(['context_sha256', 'manifest_sha256', 'manifest_byte_count'])('binds substituted result reference %s even when self-resealed', async field => {
    const m = await api(), f = fixture(), ref = f.value.result_references.current13
    ref[field] = field === 'manifest_byte_count' ? ref[field] + 1 : '1'.repeat(64)
    f.value.views.current13.result_reference = clone(ref); seal(f.value)
    expect(() => m.validateLearnedView(f.value, f.old)).toThrowError(expect.objectContaining({ code: 'IDENTITY_MISMATCH' }))
  })
  it('gates commit after a reentrant retry during detached rendering', async () => {
    const m = await api(), f = fixture(), root = document.createElement('main'); document.body.append(root)
    const fetch = vi.fn(async (url: string) => response(url.startsWith('/release-if-learned') ? f.value : f.old))
    const h = m.mountReleaseIFLearnedView(root, { fetchImpl: fetch }); handles.push(h)
    const trigger = document.createElement('button'); trigger.dataset.action = 'retry'; root.append(trigger)
    const real = document.createElement.bind(document); let fired = false
    vi.spyOn(document, 'createElement').mockImplementation(((tag: string, options?: ElementCreationOptions) => {
      if (tag === 'section' && !fired) { fired = true; trigger.click() }
      return real(tag, options)
    }) as Document['createElement'])
    await flush(); await flush(); expect(fetch).toHaveBeenCalledTimes(4); expect(root.dataset.state).toBe('ready'); expect(root.querySelectorAll('[data-view-card]')).toHaveLength(2)
  })
  it.each(['fetch', 'read', 'digest'])('delta prioritizes TIMEOUT for a late rejected %s before its timer is delivered', async stage => {
    const f = fixture(), pending = deferred<any>(); let clock = 0
    const digest = vi.fn(() => pending.promise)
    if (stage === 'digest') vi.stubGlobal('crypto', { subtle: { digest } })
    const fetch = async (url: string) => {
      if (stage === 'fetch' && url.startsWith('/release-if-learned')) return pending.promise
      if (stage === 'read' && url.startsWith('/release-if-learned')) return { status: 200, headers: new Headers({ 'Content-Type': 'application/json' }),
        body: { getReader: () => ({ read: () => pending.promise, cancel: async () => {}, releaseLock() {} }) } }
      return response(url.startsWith('/release-if-learned') ? f.value : f.old)
    }
    const { root } = await mount(fetch, { now: () => clock, setTimeoutImpl: () => 17, clearTimeoutImpl: vi.fn(), noCrypto: true })
    clock = 10001; pending.reject(new Error('late private rejection')); await flush(false)
    expect(root.dataset.state).toBe('error'); expect(root.dataset.errorCode).toBe('TIMEOUT'); expect(root.querySelector('a')).toBeNull()
    if (stage === 'digest') expect(digest).toHaveBeenCalledTimes(1)
  })
  it.each(['fetch', 'read'])('delta handles prompt hostile %s rejection without inspecting its prototype or properties', async stage => {
    const f = fixture(), callbacks: string[] = []
    const hostile = new Proxy({}, { getPrototypeOf() { callbacks.push('prototype'); throw new Error('private prototype') }, get() { callbacks.push('property'); throw new Error('private property') } })
    const { root } = await mount(async (url: string) => {
      if (!url.startsWith('/release-if-learned')) return response(f.old)
      if (stage === 'fetch') return Promise.reject(hostile)
      return { status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), body: { getReader: () => ({ read: () => Promise.reject(hostile), cancel: async () => {}, releaseLock() {} }) } }
    })
    expect(callbacks).toEqual([]); expect(root.dataset.state).toBe('error'); expect(root.dataset.errorCode).toBe('FETCH_FAILED')
    expect(root.querySelector('[data-action="retry"]')).not.toBeNull(); expect(root.textContent).not.toContain('private')
  })
  it('delta preserves a replacement mount created synchronously while the retiring mount aborts', async () => {
    const m = await api(), root = document.createElement('main'); document.body.append(root)
    let replacement: { destroy(): void } | undefined, reentered = false
    const h = m.mountReleaseIFLearnedView(root, { fetchImpl: (_url: string, init: RequestInit) => {
      init.signal?.addEventListener('abort', () => {
        if (reentered) return; reentered = true
        replacement = m.mountReleaseIFLearnedView(root, { fetchImpl: () => new Promise(() => {}) })
        if (replacement) handles.push(replacement)
      }, { once: true })
      return new Promise(() => {})
    } }); handles.push(h); await flush(false); h.destroy(); await flush(false)
    expect(replacement).toBeDefined(); expect(replacement).not.toBe(h); expect(root.dataset.state).toBe('loading'); expect(root.getAttribute('aria-busy')).toBe('true')
    h.destroy(); expect(root.dataset.state).toBe('loading'); expect(root.getAttribute('aria-busy')).toBe('true')
  })
  it('delta stops a retry start when abort synchronously destroys and remounts its owner', async () => {
    vi.useFakeTimers(); const m = await api(), root = document.createElement('main'); document.body.append(root)
    const timer = vi.fn((callback: () => void, ms: number) => setTimeout(callback, ms)); let entered = false
    const h = m.mountReleaseIFLearnedView(root, { setTimeoutImpl: timer, fetchImpl: (_url: string, init: RequestInit) => {
      init.signal?.addEventListener('abort', () => {
        if (entered) return; entered = true; h.destroy()
        const next = m.mountReleaseIFLearnedView(root, { fetchImpl: () => new Promise(() => {}) }); handles.push(next)
      }, { once: true }); return new Promise(() => {})
    } }); handles.push(h); await flush(false)
    const trigger = document.createElement('button'); trigger.dataset.action = 'retry'; root.append(trigger); trigger.click(); await flush(false)
    expect(timer).toHaveBeenCalledTimes(1); expect(root.dataset.state).toBe('loading'); expect(root.getAttribute('aria-busy')).toBe('true')
    h.destroy(); expect(root.dataset.state).toBe('loading')
  })
  it('admission deadline rejects before any fetch chain exists without unhandled rejection', async () => {
    const m = await api(), root = document.createElement('main'); document.body.append(root)
    const fetch = vi.fn(), unhandled: unknown[] = [], listener = (reason: unknown) => { unhandled.push(reason) }
    const now = vi.fn().mockReturnValueOnce(0).mockReturnValue(10001)
    process.on('unhandledRejection', listener)
    try {
      const h = m.mountReleaseIFLearnedView(root, { fetchImpl: fetch, now, setTimeoutImpl: () => 41, clearTimeoutImpl: vi.fn() }); handles.push(h)
      await flush(false); await new Promise(resolve => setTimeout(resolve, 0))
      expect(fetch).not.toHaveBeenCalled(); expect(root.dataset.state).toBe('error'); expect(root.dataset.errorCode).toBe('TIMEOUT')
      expect(root.getAttribute('aria-busy')).toBe('false'); expect(root.querySelector('[data-action="retry"]')).not.toBeNull()
      expect(root.querySelector('a')).toBeNull(); expect(unhandled).toEqual([])
    } finally { process.removeListener('unhandledRejection', listener) }
  })
})

describe('learned view actual backend byte bridge', () => {
  it('compares actual backend bytes with a numeric-only two-token negative control', async () => {
    const interpreter = resolve(ROOT, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python')
    const script = String.raw`
import base64,json,sys
from fastapi.testclient import TestClient
from tests.backend.test_release_if_learned_view import hand_tuple
from traffic_api.release_if_learned_view import create_release_if_learned_view_app
app=create_release_if_learned_view_app(*hand_tuple())
with TestClient(app) as client:
 a=client.get('/release-if-learned/v1/summary');b=client.get('/release-if/v1/summary')
 for response,limit in ((a,65536),(b,16384)):
  assert response.status_code==200
  assert response.headers['content-type'].split(';')[0].strip().lower()=='application/json'
  assert len(response.content)<=limit and not response.content.startswith(b'\xef\xbb\xbf')
  response.content.decode('utf-8','strict')
 value=json.loads(a.content);del value['snapshot_sha256']
 pre=(json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')
 result={name:base64.b64encode(body).decode('ascii') for name,body in (('learned_body_b64',a.content),('result_body_b64',b.content),('learned_preimage_b64',pre))}
 data=(json.dumps(result,separators=(',',':'))+'\n').encode('ascii');assert len(data)<=262144
 sys.stdout.buffer.write(data)
`
    const env = { ...process.env, PYTHONPATH: [ROOT, resolve(ROOT, 'src/core'), resolve(ROOT, 'src/backend')].join(delimiter),
      PYTHONDONTWRITEBYTECODE: '1', PYTHONNOUSERSITE: '1', PYTHONOPTIMIZE: '0', OMP_NUM_THREADS: '1', MKL_NUM_THREADS: '1', OPENBLAS_NUM_THREADS: '1' }
    const child = spawnSync(interpreter, ['-X', 'utf8', '-B', '-c', script], { cwd: ROOT, env, timeout: 30000, maxBuffer: 1048576 })
    expect(child.error).toBeUndefined(); expect(child.status, child.stderr?.toString('utf8')).toBe(0)
    expect(child.stdout.byteLength).toBeLessThanOrEqual(262144); expect(child.stderr.byteLength).toBeLessThanOrEqual(1048576)
    const payload = JSON.parse(child.stdout.toString('ascii')), decode = (name: string) => new Uint8Array(Buffer.from(payload[name], 'base64'))
    expect(Object.keys(payload).sort()).toEqual(['learned_body_b64', 'learned_preimage_b64', 'result_body_b64'])
    const a = decode('learned_body_b64'), b = decode('result_body_b64'), pre = decode('learned_preimage_b64')
    expect(a.byteLength).toBeLessThanOrEqual(65536); expect(b.byteLength).toBeLessThanOrEqual(16384)
    expect([...a.slice(0, 3)]).not.toEqual([239, 187, 191]); expect([...b.slice(0, 3)]).not.toEqual([239, 187, 191])
    const value = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(a)), old = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(b)), m = await api()
    expect([...m.canonicalLearnedViewBytes(value)]).toEqual([...pre]); expect(await m.verifyLearnedView(value, old)).toBe(value)
    const text = new TextDecoder('utf-8', { fatal: true }).decode(pre); expect(text.match(/"max_features":1\.0/g)).toHaveLength(2)
    for (const view of VIEWS) expect(value.views[view].declarations.model_configuration.max_features).toBe(1)
    const negative = text.replaceAll('"max_features":1.0', '"max_features":1')
    expect(negative.replaceAll('"max_features":1', '"max_features":1.0')).toBe(text)
    expect(hash(pre)).toBe(value.snapshot_sha256); expect(hash(negative)).not.toBe(value.snapshot_sha256)
    for (const name of ['learned.html', 'learned.mjs', 'learned.css']) expect(readFileSync(resolve(ASSETS, name)).byteLength).toBeLessThanOrEqual(65536)
  }, 40000)
})
