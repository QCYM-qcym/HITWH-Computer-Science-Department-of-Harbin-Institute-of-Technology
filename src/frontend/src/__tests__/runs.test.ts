import { afterEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMockApi } from '../api/mock'
import { followRun } from '../api/polling'
import { useWorkspaceStore } from '../stores/workspace'

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })
describe('task lifecycle', () => {
  it('observes queued / running / succeeded then stops polling', async () => {
    vi.useFakeTimers()
    const api = createMockApi()
    const seen: string[] = []
    followRun(api, 'synthetic-run', { onStatus: s => seen.push(s.status), onError: e => { throw e }, interval: 100 })
    await vi.advanceTimersByTimeAsync(500)
    expect(seen).toEqual(['queued', 'running', 'succeeded'])
    await vi.advanceTimersByTimeAsync(1000)
    expect(seen).toHaveLength(3)
  })
  it('shows failure and never keeps polling a terminal failed run', async () => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    const store = useWorkspaceStore()
    store.setApi(createMockApi('failed'))
    await store.initialize()
    await store.submit({ dataset_id: 'synthetic-v1', split_id: 'split-v1', method: 'iforest', config_id: 'smoke-v1' })
    await vi.advanceTimersByTimeAsync(3000)
    expect(store.activeRun?.status).toBe('failed')
    expect(store.activeRun?.error?.code).toBe('WORKER_INTERRUPTED')
    expect(store.tracking).toBe(false)
    expect(store.series).toBeNull()
  })
  it('unsubscribing stops pending updates without pretending the backend cancelled', async () => {
    vi.useFakeTimers()
    const api = createMockApi()
    const seen: string[] = []
    const stop = followRun(api, 'synthetic-run', { onStatus: s => seen.push(s.status), onError: e => { throw e }, interval: 100 })
    await vi.advanceTimersByTimeAsync(0)
    stop()
    await vi.advanceTimersByTimeAsync(1000)
    expect(seen).toEqual(['queued'])
    expect((await api.status('synthetic-run')).status).toBe('running')
  })
  it('stops on a network error and does not publish a late response after unsubscribe', async () => {
    vi.useFakeTimers()
    const api = createMockApi()
    let release: (() => void) | undefined
    const realStatus = api.status
    api.status = async (id) => { await new Promise<void>(resolve => { release = resolve }); return realStatus(id) }
    const seen: string[] = []
    const stop = followRun(api, 'synthetic-run', { onStatus: s => seen.push(s.status), onError: () => seen.push('error'), interval: 100 })
    stop(); release!()
    await vi.advanceTimersByTimeAsync(1000)
    expect(seen).toEqual([])
    api.status = async () => { throw new Error('offline') }
    followRun(api, 'synthetic-run', { onStatus: s => seen.push(s.status), onError: () => seen.push('error'), interval: 100 })
    await vi.advanceTimersByTimeAsync(1000)
    expect(seen).toEqual(['error'])
  })
  it('clears previous result loading state when switching away during a slow request', async () => {
    setActivePinia(createPinia())
    const store = useWorkspaceStore(), api = createMockApi(), series = api.series
    let release: (() => void) | undefined
    api.series = async (id, query) => { await new Promise<void>(resolve => { release = resolve }); return series(id, query) }
    store.setApi(api)
    const opening = store.openRun('synthetic-succeeded')
    await Promise.resolve(); await Promise.resolve()
    expect(store.loading).toBe(true)
    await store.openRun('synthetic-failed')
    release!(); await opening
    expect(store.activeRun?.status).toBe('failed')
    expect(store.series).toBeNull()
    expect(store.loading).toBe(false)
  })
  it('downloads the requested run under its own filename even after the active task changes', async () => {
    setActivePinia(createPinia())
    const store = useWorkspaceStore(), api = createMockApi()
    let release: (() => void) | undefined
    api.download = async () => { await new Promise<void>(resolve => { release = resolve }); return new Blob(['fixture']) }
    const savedNames: string[] = []
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { savedNames.push(this.download) })
    const BrowserURL = URL
    vi.stubGlobal('URL', class extends BrowserURL { static createObjectURL() { return 'blob:fixture' } static revokeObjectURL() {} })
    store.setApi(api); await store.openRun('synthetic-succeeded')
    const downloading = store.download('metrics')
    await store.openRun('synthetic-failed')
    release!(); await downloading
    expect(savedNames).toEqual(['synthetic-succeeded-metrics.json'])
  })
})
