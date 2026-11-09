import { afterEach, describe, expect, it, vi } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import fixture from '@fixtures/release-input-view-summary-v1.json'

const DIRECTORY = resolve(dirname(fileURLToPath(import.meta.url)), '../../../backend/traffic_api/release_static')
const FILE = resolve(DIRECTORY, 'inputs.mjs')
const ENDPOINT = '/release/v1/input-summary'
const QUALIFICATIONS = ['train_full_history_normal', 'calibration_full_history_normal',
  'validation_current_normal', 'validation_current_attack', 'validation_current_unknown',
  'test_current_normal', 'test_current_attack', 'test_current_unknown']
const POLICIES = ['P_U', 'P_B', 'P_A']
const MINUTES = ['total', 'raw_valid', 'prepared_valid', 'common_valid', 'history_h15_valid', 'history_h30_valid']
type Handle = { destroy(): void }
type Fetcher = (url: string, init: RequestInit) => Promise<unknown>
let modulePromise: Promise<any> | undefined
const handles: Handle[] = []
async function api() {
  expect(existsSync(FILE), 'release viewer module must exist').toBe(true)
  return modulePromise ??= import(/* @vite-ignore */ `data:text/javascript;base64,${Buffer.from(readFileSync(FILE)).toString('base64')}`)
}
async function flush() { for (let i = 0; i < 64; i++) await Promise.resolve() }
const bytes = (value: unknown) => new TextEncoder().encode(JSON.stringify(value) + '\n')
const response = (value: unknown, headers: Record<string, string> = {}) => new Response(bytes(value), {
  headers: { 'Content-Type': 'application/json; charset=utf-8', ...headers },
})
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void
  const promise = new Promise<T>((a, b) => { resolve = a; reject = b })
  return { promise, resolve, reject }
}
async function mount(fetchImpl: Fetcher = async () => response(fixture.cases.general)) {
  const module = await api(), root = document.createElement('main')
  document.body.append(root)
  const handle = module.mountReleaseInputView(root, { fetchImpl })
  handles.push(handle)
  await flush()
  return { root, handle }
}
function errorText(root: HTMLElement) { return root.querySelector('#input-error')?.textContent ?? '' }
function expectRejected(root: HTMLElement) {
  expect(errorText(root)).toMatch(/格式不匹配|读取失败|超出读取上限/)
  expect(root.querySelector('#input-content')?.childElementCount ?? 0).toBe(0)
  expect(root.querySelectorAll('img,svg,iframe,script')).toHaveLength(0)
  expect(root.textContent).not.toContain('PRIVATE_TOKEN')
}
afterEach(() => {
  for (const handle of handles.splice(0)) handle.destroy()
  document.body.replaceChildren()
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('release input saved-summary view', () => {
  it('accepts the native fetch byte-view realm as well as DOM-created chunks', async () => {
    const native = response(fixture.cases.general)
    const reader = native.body!.getReader()
    const chunk = (await reader.read()).value
    expect(ArrayBuffer.isView(chunk)).toBe(true)
    expect(Object.prototype.toString.call(chunk)).toBe('[object Uint8Array]')
    await reader.cancel(); reader.releaseLock()
    const { root } = await mount()
    expect(errorText(root)).toBe('')
    expect(root.querySelectorAll('#input-qualifications tbody tr')).toHaveLength(8)
  })
  it.each(['general', 'zero_calibration'] as const)('renders %s with eight rows, original counts and all scope limits', async name => {
    const value = fixture.cases[name], fetcher = vi.fn(async (_url: string, _init: RequestInit) => response(value))
    const { root } = await mount(fetcher)
    expect(root.querySelectorAll('#input-qualifications tbody tr')).toHaveLength(8)
    expect(errorText(root)).toBe('')
    const summary = value.summary
    for (const key of MINUTES) expect(root.querySelector(`[data-count="${key}"]`)?.textContent)
      .toBe(String(summary.minute_counts[key as keyof typeof summary.minute_counts]))
    expect(root.querySelector('[data-fit-count]')?.textContent).toBe(String(summary.fit.count))
    for (const policy of POLICIES) for (const key of QUALIFICATIONS) {
      const counts = summary.qualification_counts[policy as keyof typeof summary.qualification_counts]
      expect(root.querySelector(`[data-policy="${policy}"][data-qualification="${key}"]`)?.textContent)
        .toBe(String(counts[key as keyof typeof counts]))
    }
    for (const identity of [summary.identity, summary.upstream_identity]) {
      for (const value of Object.values(identity)) expect(root.textContent).toContain(String(value))
    }
    for (const hash of [summary.configuration_sha256, summary.fit.mask_sha256, summary.fit.rows_sha256])
      expect(root.textContent).toContain(hash)
    for (const text of ['P_U', 'P_B', 'P_A', 'NOT_AUTHENTICATED', 'SOURCE_WALL_CLOCK_COMPLETION_PROXY',
      'AUDIT_ONLY', 'SAVED_INPUT_INTERNAL_CONSISTENCY_ONLY', 'NOT_PERFORMED', 'NOT_REESTIMATED',
      '未认证', '非认证 UTC', '未重放', '未重估', '零校准不表示评价比率为零']) expect(root.textContent).toContain(text)
    expect(root.textContent).not.toMatch(/误报率|允许训练|研究通过|0%|SYNTHETIC_ONLY|REAL_DATA/)
    expect(root.querySelector('#input-qualifications')?.getAttribute('tabindex')).toBe('0')
    expect(root.querySelector('#input-qualifications')?.getAttribute('role')).toBe('region')
    expect(root.querySelectorAll('thead th[scope="col"]')).toHaveLength(4)
    expect(root.querySelectorAll('tbody th[scope="row"]')).toHaveLength(8)
    expect(root.querySelector('#input-status')?.getAttribute('aria-live')).toBe('polite')
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(fetcher.mock.calls[0]?.[0]).toBe(ENDPOINT)
  })

  it('uses one fixed same-origin GET and does not mount automatically on a test import', async () => {
    const globalFetch = vi.spyOn(globalThis, 'fetch')
    await api()
    expect(globalFetch).not.toHaveBeenCalled()
    const fetcher = vi.fn(async (_url: string, _init: RequestInit) => response(fixture.cases.general))
    const { root, handle } = await mount(fetcher)
    const init = fetcher.mock.calls[0]?.[1]
    expect(fetcher.mock.calls.map(call => call[0])).toEqual([ENDPOINT])
    expect(init).toMatchObject({ method: 'GET', headers: { Accept: 'application/json' },
      cache: 'no-store', credentials: 'same-origin', redirect: 'error' })
    expect(init?.signal).toBeDefined()
    const again = (await api()).mountReleaseInputView(root, { fetchImpl: fetcher })
    expect(again).toBe(handle)
    await flush()
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(root.querySelectorAll('button')).toHaveLength(0)
  })

  it.each(['missing', 'tiny', 'huge'])('accepts exactly 65536 actual streamed bytes with %s Content-Length', async mode => {
    const prefix = bytes(fixture.cases.general), padded = new Uint8Array(65536).fill(32)
    padded.set(prefix)
    const body = new ReadableStream<Uint8Array>({ start(c) {
      c.enqueue(padded.subarray(0, 17)); c.enqueue(padded.subarray(17, 32768));
      c.enqueue(padded.subarray(32768)); c.close()
    } })
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (mode !== 'missing') headers['Content-Length'] = mode === 'tiny' ? '1' : '999999999'
    const { root } = await mount(async () => new Response(body, { headers }))
    expect(root.querySelectorAll('#input-qualifications tbody tr')).toHaveLength(8)
    expect(errorText(root)).toBe('')
  })

  it('rejects 65537 actual chunked bytes and cancels the reader despite a small length header', async () => {
    const cancel = vi.fn(), extra = new Uint8Array(65537).fill(32)
    extra.set(bytes(fixture.cases.general))
    const body = new ReadableStream<Uint8Array>({ start(c) {
      c.enqueue(extra.subarray(0, 65536)); c.enqueue(extra.subarray(65536))
    }, cancel })
    let signal: AbortSignal | undefined
    const { root } = await mount(async (_url, init) => {
      signal = init.signal ?? undefined
      return new Response(body, { headers: { 'Content-Type': 'application/json', 'Content-Length': '1' } })
    })
    expectRejected(root)
    expect(errorText(root)).toContain('超出读取上限')
    expect(cancel).toHaveBeenCalledTimes(1)
    expect(signal?.aborted).toBe(true)
  })

  const malformed: Array<[string, (value: any) => void]> = [
    ['extra envelope key', x => { x.private = '<img src=x onerror=PRIVATE_TOKEN>' }],
    ['extra summary key', x => { x.summary.matrix = [] }],
    ['version', x => { x.version = 2 }], ['command', x => { x.command = 'verify' }],
    ['status', x => { x.status = 'MATCHED' }], ['replay', x => { x.replay = {} }],
    ['prepared profile', x => { x.summary.identity.profile_id = 'c17-release-minute-package-v1' }],
    ['upstream profile', x => { x.summary.upstream_identity.profile_id = 'other' }],
    ['identity markup', x => { x.summary.identity.context_sha256 = '<svg onload=PRIVATE_TOKEN>' }],
    ['uppercase SHA', x => { x.summary.identity.manifest_sha256 = 'A'.repeat(64) }],
    ['SHA newline', x => { x.summary.fit.rows_sha256 += '\n' }],
    ['zero manifest bytes', x => { x.summary.identity.manifest_byte_count = 0 }],
    ['unsafe manifest bytes', x => { x.summary.upstream_identity.manifest_byte_count = Number.MAX_SAFE_INTEGER + 1 }],
    ['configuration hash', x => { x.summary.configuration_sha256 = 'bad' }],
    ['authentication', x => { x.summary.source_authentication = 'AUTHENTICATED' }],
    ['time basis', x => { x.summary.time_basis = 'UTC' }],
    ['feature count', x => { x.summary.configuration.feature_count = 26 }],
    ['windows', x => { x.summary.configuration.windows = [30, 15] }],
    ['fit window', x => { x.summary.configuration.fit_window = 15 }],
    ['schema version', x => { x.summary.configuration.schema_version = true }],
    ['numeric rules', x => { x.summary.configuration.numeric_rules_id = 'other' }],
    ['epsilon zero', x => { x.summary.configuration.epsilon = 0 }],
    ['epsilon null', x => { x.summary.configuration.epsilon = null }],
    ['epsilon string', x => { x.summary.configuration.epsilon = '0.000001' }],
    ['audit fit policy', x => { x.summary.configuration.audit_fit_policy = 'best' }],
    ['policy status', x => { x.summary.configuration.policy_status = 'APPROVED' }],
    ['extra configuration', x => { x.summary.configuration.approved = true }],
    ['zero total', x => { x.summary.minute_counts.total = 0 }],
    ['count float', x => { x.summary.minute_counts.raw_valid = 0.5 }],
    ['count bool', x => { x.summary.minute_counts.prepared_valid = false }],
    ['count null', x => { x.summary.minute_counts.common_valid = null }],
    ['count negative', x => { x.summary.minute_counts.history_h15_valid = -1 }],
    ['count over bound', x => { x.summary.fit.count = 10001 }],
    ['missing minute field', x => { delete x.summary.minute_counts.history_h30_valid }],
    ['fit hash', x => { x.summary.fit.mask_sha256 = 'x'.repeat(64) }],
    ['missing policy', x => { delete x.summary.qualification_counts.P_B }],
    ['extra qualification', x => { x.summary.qualification_counts.P_A.fpr = 0 }],
    ['qualification string', x => { x.summary.qualification_counts.P_U.test_current_unknown = '2' }],
    ['check scope', x => { x.summary.package_checks.scope = 'RESEARCH_APPROVED' }],
    ['check byte integrity', x => { x.summary.package_checks.byte_integrity = 'NOT_CHECKED' }],
    ['check structure', x => { x.summary.package_checks.structure = 'NOT_CHECKED' }],
    ['check status', x => { x.summary.package_checks.status = 'MATCHED' }],
    ['check upstream replay', x => { x.summary.package_checks.upstream_replay = 'MATCHED' }],
    ['check transform replay', x => { x.summary.package_checks.transform_history_replay = 'MATCHED' }],
    ['check parameters', x => { x.summary.package_checks.fit_parameters = 'REESTIMATED' }],
  ]
  it.each(malformed)('rejects malformed %s before rendering partial data', async (_name, change) => {
    const value = structuredClone(fixture.cases.general)
    change(value)
    const { root } = await mount(async () => response(value))
    expectRejected(root)
    expect(root.textContent).not.toContain('1111111111111111')
  })

  it.each(['utf8', 'json', 'media', 'missing media', 'http', 'missing stream', 'no stream reader', 'nonbyte chunk', 'network'])('safely rejects %s without text/json fallback or private error content', async kind => {
    const text = vi.fn(), json = vi.fn()
    const { root } = await mount(async () => {
      if (kind === 'network') throw Error('PRIVATE_TOKEN <img src=x> C:/private/secret')
      if (kind === 'utf8') return new Response(new Uint8Array([255, 254]), { headers: { 'Content-Type': 'application/json' } })
      if (kind === 'json') return new Response('{PRIVATE_TOKEN<img>', { headers: { 'Content-Type': 'application/json' } })
      if (kind === 'media') return response(fixture.cases.general, { 'Content-Type': 'text/html' })
      if (kind === 'missing media') return new Response(bytes(fixture.cases.general))
      if (kind === 'http') return new Response('PRIVATE_TOKEN<img>', { status: 500, headers: { 'Content-Type': 'application/json' } })
      if (kind === 'nonbyte chunk') return { status: 200, headers: new Headers({ 'Content-Type': 'application/json' }),
        body: { getReader: () => ({ read: async () => ({ done: false, value: 'PRIVATE_TOKEN' }), cancel: async () => {}, releaseLock() {} }) } }
      return { status: 200, headers: new Headers({ 'Content-Type': 'application/json' }),
        body: kind === 'missing stream' ? null : {}, text, json }
    })
    expectRejected(root)
    expect(text).not.toHaveBeenCalled()
    expect(json).not.toHaveBeenCalled()
  })

  it.each(['destroy', 'pagehide'] as const)('cancels a pending fetch on %s and drops a late success', async action => {
    const pending = deferred<unknown>(), fetcher = vi.fn((_url: string, _init: RequestInit) => pending.promise)
    const { root, handle } = await mount(fetcher)
    expect(fetcher).toHaveBeenCalledTimes(1)
    if (action === 'destroy') handle.destroy(); else window.dispatchEvent(new Event('pagehide'))
    const snapshot = root.textContent
    expect(fetcher.mock.calls[0]?.[1].signal?.aborted).toBe(true)
    pending.resolve(response(fixture.cases.general))
    await flush()
    expect(root.textContent).toBe(snapshot)
    expect(root.querySelectorAll('#input-qualifications tbody tr')).toHaveLength(0)
    expect(errorText(root)).toBe('')
  })

  it.each(['resolve', 'reject'] as const)('cancels a pending body and ignores late %s after destroy', async outcome => {
    const pending = deferred<{ done: boolean, value?: Uint8Array }>()
    const cancel = vi.fn(async () => {}), read = vi.fn(() => pending.promise), releaseLock = vi.fn()
    const { root, handle } = await mount(async () => ({ status: 200,
      headers: new Headers({ 'Content-Type': 'application/json' }), body: { getReader: () => ({ read, cancel, releaseLock }) } }))
    handle.destroy()
    const snapshot = root.textContent
    expect(cancel).toHaveBeenCalledTimes(1)
    if (outcome === 'resolve') pending.resolve({ done: false, value: bytes(fixture.cases.general) })
    else pending.reject(Error('PRIVATE_TOKEN late rejection'))
    await flush()
    expect(read).toHaveBeenCalledTimes(1)
    expect(releaseLock).toHaveBeenCalledTimes(1)
    expect(root.textContent).toBe(snapshot)
    expect(errorText(root)).toBe('')
  })

  it('applies one 10-second deadline across fetch and body, cancels reader and leaves no timers/listeners', async () => {
    await api()
    vi.useFakeTimers()
    const fetchPending = deferred<unknown>(), bodyPending = deferred<{ done: boolean }>()
    const cancel = vi.fn(async () => {}), releaseLock = vi.fn()
    const remove = vi.spyOn(window, 'removeEventListener')
    let signal: AbortSignal | undefined
    const fetcher = vi.fn((_url: string, init: RequestInit) => { signal = init.signal ?? undefined; return fetchPending.promise })
    const { root } = await mount(fetcher)
    await vi.advanceTimersByTimeAsync(9500)
    expect(errorText(root)).toBe('')
    fetchPending.resolve({ status: 200, headers: new Headers({ 'Content-Type': 'application/json' }),
      body: { getReader: () => ({ read: () => bodyPending.promise, cancel, releaseLock }) } })
    await flush()
    await vi.advanceTimersByTimeAsync(500)
    await flush()
    expect(errorText(root)).toContain('读取超时')
    expect(signal?.aborted).toBe(true)
    expect(cancel).toHaveBeenCalledTimes(1)
    expect(releaseLock).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
    expect(remove.mock.calls.some(call => call[0] === 'pagehide')).toBe(true)
    bodyPending.resolve({ done: true })
    await flush()
    expect(errorText(root)).toContain('读取超时')
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('times out a noncooperative fetch and ignores its later rejection', async () => {
    await api(); vi.useFakeTimers()
    const pending = deferred<unknown>(), fetcher = vi.fn(() => pending.promise)
    const { root } = await mount(fetcher)
    await vi.advanceTimersByTimeAsync(10000)
    expect(errorText(root)).toContain('读取超时')
    const snapshot = root.textContent
    pending.reject(Error('PRIVATE_TOKEN'))
    await flush()
    expect(root.textContent).toBe(snapshot)
    expect(vi.getTimerCount()).toBe(0)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('checks a monotonic deadline during immediately resolved empty reads, before the timer can run', async () => {
    let clock = 0, reads = 0
    vi.spyOn(performance, 'now').mockImplementation(() => clock)
    const cancel = vi.fn(async () => {}), releaseLock = vi.fn()
    const read = vi.fn(async () => {
      clock += 5000
      return ++reads <= 3 ? { done: false, value: new Uint8Array(0) } : { done: true }
    })
    const { root } = await mount(async () => ({ status: 200, headers: new Headers({ 'Content-Type': 'application/json' }),
      body: { getReader: () => ({ read, cancel, releaseLock }) } }))
    expect(errorText(root)).toContain('读取超时')
    expect(read).toHaveBeenCalledTimes(2)
    expect(cancel).toHaveBeenCalledTimes(1)
    expect(releaseLock).toHaveBeenCalledTimes(1)
    expect(root.querySelectorAll('#input-qualifications tbody tr')).toHaveLength(0)
  })

  it('cleans success lifetime listeners and timer, including an idempotent destroy', async () => {
    await api(); vi.useFakeTimers()
    const remove = vi.spyOn(window, 'removeEventListener')
    const { root, handle } = await mount()
    expect(root.querySelectorAll('#input-qualifications tbody tr')).toHaveLength(8)
    expect(vi.getTimerCount()).toBe(0)
    expect(remove.mock.calls.some(call => call[0] === 'pagehide')).toBe(true)
    handle.destroy(); handle.destroy()
    await vi.advanceTimersByTimeAsync(20000)
    expect(errorText(root)).toBe('')
  })

  it('ships exactly local resources, no inline/external code, readable hashes and a keyboard-scroll region', async () => {
    const html = readFileSync(resolve(DIRECTORY, 'inputs.html'), 'utf8')
    const css = readFileSync(resolve(DIRECTORY, 'inputs.css'), 'utf8')
    const js = readFileSync(FILE, 'utf8')
    const parsed = new DOMParser().parseFromString(html, 'text/html')
    expect(parsed.title).toBe('输入包检查')
    expect(parsed.querySelector('html')?.lang).toBe('zh-CN')
    expect(parsed.querySelector('meta[name="viewport"]')).not.toBeNull()
    expect(parsed.querySelectorAll('script')).toHaveLength(1)
    expect(parsed.querySelector('script')?.getAttribute('src')).toBe('/release/inputs.mjs')
    expect(parsed.querySelector('script')?.getAttribute('type')).toBe('module')
    expect(parsed.querySelector('script')?.textContent?.trim()).toBe('')
    expect(parsed.querySelector('link')?.getAttribute('href')).toBe('/release/inputs.css')
    expect(parsed.querySelector('noscript')?.textContent).toContain('JavaScript')
    expect(parsed.querySelectorAll('style,[onclick],iframe,img')).toHaveLength(0)
    expect(js).not.toMatch(/innerHTML|\beval\s*\(|new\s+Function|\.text\s*\(|\.json\s*\(/)
    expect(html + css).not.toMatch(/https?:\/\/|@import|url\s*\(/)
    expect(css).toMatch(/overflow-x:\s*auto/)
    expect(css).toMatch(/overflow-wrap:\s*anywhere/)
    expect(css).toContain(':focus-visible')
    for (const text of [html, css, js]) expect(Buffer.byteLength(text, 'utf8')).toBeLessThanOrEqual(65536)
  })
})
