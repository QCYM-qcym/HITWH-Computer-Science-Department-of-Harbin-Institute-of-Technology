import { ApiError, decode } from './contract'
import type { ExportKind, Query, Schemas, TrafficApi } from '../types'

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
export function createHttpApi(fetcher: Fetcher = globalThis.fetch.bind(globalThis)): TrafficApi {
  const path = (id: string) => `/api/v1/runs/${encodeURIComponent(id)}`
  const search = (query: Query) => {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) if (value !== undefined && value !== '') params.set(key, String(value))
    return params.size ? '?' + params : ''
  }
  async function request<K extends keyof Schemas>(url: string, schema: K, init?: RequestInit): Promise<Schemas[K]> {
    const response = await fetcher(url, init)
    const body: unknown = await response.json()
    if (!response.ok) { const { error } = decode('ErrorResponse', body); throw new ApiError(error.code, error.message) }
    return decode(schema, body)
  }
  return {
    datasets: () => request('/api/v1/datasets', 'DatasetList'),
    submit: (input) => {
      const checked = decode('RunRequest', input)
      return request('/api/v1/runs', 'RunAccepted', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(checked) })
    },
    status: (id, signal) => request(path(id), 'RunStatus', { signal }),
    series: (id, query) => request(path(id) + '/series' + search(query), 'SeriesPage'),
    alarms: (id, query) => request(path(id) + '/alarms' + search(query), 'SeriesPage'),
    evaluation: (id) => request(path(id) + '/evaluation', 'Evaluation'),
    minute: (id, timestamp) => request(path(id) + '/minutes/' + encodeURIComponent(timestamp), 'MinuteDetail'),
    download: async (id, kind: ExportKind) => {
      if (!['scores', 'metrics', 'config'].includes(kind)) throw new ApiError('VALIDATION_ERROR', '导出类型无效。')
      const response = await fetcher(path(id) + '/exports/' + kind)
      if (!response.ok) { const { error } = decode('ErrorResponse', await response.json()); throw new ApiError(error.code, error.message) }
      return response.blob()
    },
  }
}
