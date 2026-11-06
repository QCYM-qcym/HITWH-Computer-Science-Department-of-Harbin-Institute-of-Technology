import { afterEach, describe, expect, it, vi } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import full from './fixtures/capacity-display-v1.json'
import minimal from './fixtures/capacity-display-minimal-v1.json'
import history30 from './fixtures/capacity-display-history30-v1.json'

const FILE = resolve(dirname(fileURLToPath(import.meta.url)), '../../../backend/traffic_api/candidate_static/capacity.mjs')
const ENDPOINT = '/candidate/v1/capacity-comparison'
const SLOTS = ['current_ae13', 'current_ae13_capacity492', 'history_ae26_h15', 'history_ae26_h30']
let modulePromise: Promise<any>, handle: { dispose(): void } | undefined
const node = (id: string) => document.getElementById(id)!
async function moduleApi() {
  expect(existsSync(FILE), 'capacity viewer implementation must exist').toBe(true)
  return modulePromise ??= import(/* @vite-ignore */ `data:text/javascript;base64,${Buffer.from(readFileSync(FILE)).toString('base64')}`)
}
const bytes = (value: unknown) => new TextEncoder().encode(JSON.stringify(value) + '\n')
function response(value: unknown) { return new Response(bytes(value), { headers: { 'Content-Length': '1' } }) }
async function flush() { for (let i = 0; i < 25; i++) await new Promise(resolve => setTimeout(resolve, 0)) }
async function mount(fetcher: (url: string, init: RequestInit) => Promise<unknown> = async () => response(full)) {
  const root = document.createElement('main'); document.body.append(root)
  handle = (await moduleApi()).mountCapacityViewer(root, { fetcher })
  await flush(); return root
}
function deferred<T>() { let resolve!: (value: T) => void, reject!: (reason: unknown) => void; const promise = new Promise<T>((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
afterEach(() => { handle?.dispose(); handle = undefined; document.body.replaceChildren(); vi.restoreAllMocks() })

describe('fixed capacity-only saved result viewer', () => {
  it('renders four distinct rows, per-model thresholds, full-axis versus test counts and explanatory limits', async () => {
    const fetcher = vi.fn(async (_url: string, _init: RequestInit) => response(full)), root = await mount(fetcher)
    expect(node('capacity-error').textContent).toBe('')
    const rows = [...node('capacity-table').querySelectorAll('tbody tr')]
    expect(rows.map(row => (row as HTMLElement).dataset.slot)).toEqual(SLOTS)
    expect(rows[0]!.textContent).toContain('当前特征（288参数）')
    expect(rows[1]!.textContent).toContain('当前特征（492参数）')
    expect(rows.map(row => row.children[1]!.textContent)).toEqual(['0', '0.375', '0.8', '1.25'])
    expect(node('capacity-context').textContent).toContain('全轴 144')
    expect(node('capacity-context').textContent).toContain('全轴可评分 24')
    expect(node('capacity-population').textContent).toContain('完整测试 36')
    expect(node('capacity-population').textContent).toContain('可评分 6')
    expect(node('capacity-population').textContent).toContain('未评分 30')
    expect(root.textContent).toContain('17/509'); expect(root.textContent).toContain('3.34%')
    expect(root.textContent).toContain('不代表有效容量相同'); expect(root.textContent).toContain('不进行排名')
    expect(root.querySelectorAll('.winner,.best,[data-rank]')).toHaveLength(0)
    expect(fetcher.mock.calls.map(args => args[0])).toEqual([ENDPOINT])
    expect(node('capacity-table').getAttribute('role')).toBe('region')
    expect(node('capacity-table').getAttribute('tabindex')).toBe('0')
  })
  it.each([minimal, history30])('shows both missing slots explicitly without manufactured metrics', async value => {
    await mount(async () => response(value))
    const rows = [...node('capacity-table').querySelectorAll('tbody tr')]
    expect(rows).toHaveLength(4)
    for (const row of rows) if (value.missing_slots.includes((row as HTMLElement).dataset.slot!)) {
      expect(row.textContent).toContain('未提供此运行包'); expect(row.children).toHaveLength(2)
      expect(row.textContent).not.toContain('display-')
    }
    expect(node('capacity-completeness').textContent).toContain('缺少')
    expect(node('capacity-pairs').textContent).not.toContain('当前特征（288参数） ↔')
  })
  it('keeps null reasons distinct from zero and changes only the displayed saved audit policy', async () => {
    const fetcher = vi.fn(async (_url: string, _init: RequestInit) => response(full)); await mount(fetcher)
    let row = node('capacity-table').querySelector('tbody tr')!
    expect(row.textContent).toContain('不可评价'); expect(row.textContent).toContain('没有已评分正常分钟')
    const policy = node('capacity-policy') as HTMLSelectElement
    policy.value = 'P_B'; policy.dispatchEvent(new Event('change')); await flush()
    row = node('capacity-table').querySelector('tbody tr')!
    expect([...row.children].slice(2).map(cell => cell.textContent)).toEqual(['1', '0', '4', '1', '0.0%', '50.0%'])
    policy.value = 'P_A'; policy.dispatchEvent(new Event('change')); await flush()
    expect(node('capacity-population').textContent).toContain('攻击 4')
    expect(node('capacity-context').textContent).toContain('分数来源口径 P_U')
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(node('capacity-evidence').querySelector('pre')!.textContent).toContain('"fpr": 0.5')
  })
  it.each(['classic-profile', 'extra', 'model', 'configuration', 'identity', 'threshold', 'policy', 'null-reason', 'source', 'pairs', 'order', 'limits'])('rejects malformed %s with no partial success or unsafe markup', async kind => {
    const value: any = structuredClone(full)
    if (kind === 'classic-profile') value.comparison_profile_id = 'c17-i1-g13u-comparison-context-v1'
    if (kind === 'extra') value.private_path = '<img src=x onerror=alert(1)>'
    if (kind === 'model') value.runs[1].model_profile_id = value.runs[0].model_profile_id
    if (kind === 'configuration') value.runs[1].configuration.epochs = 999
    if (kind === 'identity') value.runs[0].actual_five_artifacts['scores.json'].sha256 = 'bad'
    if (kind === 'threshold') value.runs[0].threshold = null
    if (kind === 'policy') value.runs[0].policies.P_A.normal_minutes = 99
    if (kind === 'null-reason') value.runs[0].policies.P_U.undefined_reasons.fpr = '<img src=x onerror=alert(1)>'
    if (kind === 'source') value.shared_context.source_replay = 'NOT_PROVIDED'
    if (kind === 'pairs') value.control_design.near_parameter_count_pairs = []
    if (kind === 'order') value.runs.reverse()
    if (kind === 'limits') value.limitations.ranking = 'BEST_MODEL'
    const root = await mount(async () => response(value))
    expect(node('capacity-error').textContent).toContain('格式不匹配')
    expect(node('capacity-table').children).toHaveLength(0)
    expect(node('capacity-evidence').children).toHaveLength(0)
    expect(root.querySelectorAll('img')).toHaveLength(0)
    expect(root.textContent).not.toContain('private_path')
  })
  it('retries the same endpoint, clearing old success on failure and restoring only a fresh report', async () => {
    let fail = false
    const fetcher = vi.fn(async (_url: string, _init: RequestInit) => { if (fail) throw Error('private /path credential'); return response(full) })
    await mount(fetcher); fail = true; node('capacity-retry').click(); await flush()
    expect(node('capacity-error').textContent).toContain('读取失败')
    expect(node('capacity-table').children).toHaveLength(0)
    expect(node('capacity-context').textContent).toBe('')
    expect(node('capacity-error').textContent).not.toContain('private')
    fail = false; node('capacity-retry').click(); await flush()
    expect(node('capacity-error').textContent).toBe('')
    expect(node('capacity-table').querySelectorAll('tbody tr')).toHaveLength(4)
    expect(fetcher.mock.calls.map(args => args[0])).toEqual([ENDPOINT, ENDPOINT, ENDPOINT])
  })
  it.each(['success', 'failure'])('ignores stale %s after retry and aborts its fetch signal', async outcome => {
    const first = deferred<unknown>(), second = deferred<unknown>(); let calls = 0, oldSignal: AbortSignal | undefined
    await mount(async (_url, init) => { if (calls++ === 0) { oldSignal = init.signal!; return first.promise } return second.promise })
    node('capacity-retry').click(); await flush(); expect(oldSignal?.aborted).toBe(true)
    if (outcome === 'success') first.resolve(response(full)); else first.reject(Error('private stale'))
    await flush(); expect(node('capacity-table').children).toHaveLength(0)
    expect(node('capacity-status').textContent).toContain('读取中')
    second.resolve(response(minimal)); await flush()
    expect(node('capacity-completeness').textContent).toContain('缺少')
    expect(node('capacity-error').textContent).toBe('')
  })
  it('bounds real streamed bytes independently of Content-Length, accepting exactly 1MiB and rejecting one more', async () => {
    const raw = new TextEncoder().encode(JSON.stringify(full)), exact = new Uint8Array(1048576).fill(32)
    exact.set(raw); exact[exact.length - 1] = 10
    const { readCapacityResponse } = await moduleApi()
    expect((await readCapacityResponse(new Response(exact), new AbortController().signal)).runs).toHaveLength(4)
    const cancel = vi.fn(), oversized = new Uint8Array(1048577)
    const body = new ReadableStream({ start(controller) { controller.enqueue(oversized) }, cancel })
    await expect(readCapacityResponse(new Response(body, { headers: { 'Content-Length': '1' } }), new AbortController().signal)).rejects.toThrow('RESOURCE_LIMIT')
    expect(cancel).toHaveBeenCalled()
  })
  it('rejects invalid UTF-8, absent bodies and a success-shaped error response', async () => {
    const { readCapacityResponse } = await moduleApi(), signal = new AbortController().signal
    await expect(readCapacityResponse(new Response(new Uint8Array([255, 254])), signal)).rejects.toThrow()
    await expect(readCapacityResponse(new Response(null), signal)).rejects.toThrow()
    await expect(readCapacityResponse(new Response(bytes(full), { status: 500 }), signal)).rejects.toThrow('FETCH_FAILED')
  })
  it('aborts a pending body reader and prevents a disposed page from retaining success', async () => {
    const cancel = vi.fn()
    await mount(async () => new Response(new ReadableStream({ cancel })))
    handle!.dispose(); await flush()
    expect(cancel).toHaveBeenCalled(); expect(document.querySelectorAll('#capacity-table tbody tr')).toHaveLength(0)
  })
})
