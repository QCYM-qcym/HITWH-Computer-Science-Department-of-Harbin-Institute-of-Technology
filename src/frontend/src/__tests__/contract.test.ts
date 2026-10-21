import { describe, expect, it } from 'vitest'
import fixture from '@fixtures/contracts-v1.json'
import { decode, ContractError } from '../api/contract'
import { createHttpApi } from '../api/http'
import { createMockApi } from '../api/mock'

describe('W0 contract consumer', () => {
  it('accepts every shared HTTP example and rejects unknown fields / task states', () => {
    for (const sample of fixture.responses.filter(x => ['RunAccepted', 'DatasetList', 'SeriesPage', 'Evaluation', 'MinuteDetail', 'RunStatus', 'ErrorResponse'].includes(x.schema))) {
      expect(() => decode(sample.schema as 'RunStatus', sample.body)).not.toThrow()
    }
    const status = fixture.responses.find(x => x.schema === 'RunStatus')!.body
    expect(() => decode('RunStatus', { ...status, status: 'cancelled' })).toThrow(ContractError)
    expect(() => decode('RunStatus', { ...status, path: '/private' })).toThrow(ContractError)
  })
  it('sends only registered IDs and the frozen method field', async () => {
    const requests: { url: string; init?: RequestInit }[] = []
    const api = createHttpApi(async (url, init) => {
      requests.push({ url: String(url), init })
      return new Response(JSON.stringify({ run_id: 'synthetic-run', status: 'queued' }), { status: 202 })
    })
    await api.submit(fixture.request as Parameters<typeof api.submit>[0])
    expect(requests[0]?.url).toBe('/api/v1/runs')
    expect(JSON.parse(String(requests[0]?.init?.body))).toEqual({ dataset_id: 'synthetic-v1', split_id: 'split-v1', method: 'iforest', config_id: 'smoke-v1' })
  })
  it('preserves half-open ranges and pagination instead of filtering metrics', async () => {
    const api = createMockApi()
    const page = await api.series('synthetic-run', { start: '2026-01-01T00:01:00Z', end: '2026-01-01T00:03:00Z', page: 2, page_size: 1 })
    expect(page.total).toBe(2)
    expect(page.items.map(x => x.timestamp)).toEqual(['2026-01-01T00:02:00Z'])
    expect((await api.evaluation('synthetic-run')).metrics?.fpr).toBe(0.5)
  })
  it('rejects unknown mock IDs and surfaces contract error codes', async () => {
    await expect(createMockApi().status('unknown')).rejects.toMatchObject({ code: 'NOT_FOUND' })
    const api = createHttpApi(async () => new Response(JSON.stringify({ error: { code: 'RUN_BUSY', message: 'Busy', details: [] } }), { status: 409 }))
    await expect(api.submit(fixture.request as Parameters<typeof api.submit>[0])).rejects.toMatchObject({ code: 'RUN_BUSY' })
  })
  it('does not relabel IF fixture scores as AE model output', async () => {
    await expect(createMockApi().submit({ ...fixture.request, method: 'history_ae' })).rejects.toMatchObject({ code: 'VALIDATION_ERROR' })
  })
  it('uses frozen result routes, encoded UTC minutes and explicit pagination in HTTP mode', async () => {
    const urls: string[] = []
    const api = createHttpApi(async input => {
      const url = String(input); urls.push(url)
      const schema = url.includes('/minutes/') ? 'MinuteDetail' : url.endsWith('/evaluation') ? 'Evaluation' : url.includes('/series') || url.includes('/alarms') ? 'SeriesPage' : url.includes('/runs/') ? 'RunStatus' : 'DatasetList'
      return new Response(JSON.stringify(fixture.responses.find(x => x.schema === schema)!.body))
    })
    await api.datasets(); await api.status('synthetic-run')
    await api.series('synthetic-run', { start: '2026-01-01T00:01:00Z', end: '2026-01-01T00:03:00Z', page: 2, page_size: 100 })
    await api.alarms('synthetic-run', { page: 1, page_size: 100 })
    await api.evaluation('synthetic-run'); await api.minute('synthetic-run', '2026-01-01T00:01:00Z')
    expect(urls).toEqual([
      '/api/v1/datasets', '/api/v1/runs/synthetic-run',
      '/api/v1/runs/synthetic-run/series?start=2026-01-01T00%3A01%3A00Z&end=2026-01-01T00%3A03%3A00Z&page=2&page_size=100',
      '/api/v1/runs/synthetic-run/alarms?page=1&page_size=100',
      '/api/v1/runs/synthetic-run/evaluation', '/api/v1/runs/synthetic-run/minutes/2026-01-01T00%3A01%3A00Z',
    ])
  })
  it('rejects an arbitrary server path before sending a request', () => {
    const api = createHttpApi(async () => { throw new Error('Request must not be sent') })
    expect(() => api.submit({ ...fixture.request, method: 'iforest', path: '/private' } as Parameters<typeof api.submit>[0])).toThrow(ContractError)
  })
})
