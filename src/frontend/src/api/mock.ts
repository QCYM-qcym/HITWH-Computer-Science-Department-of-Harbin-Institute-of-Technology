import fixture from '@fixtures/contracts-v1.json'
import { ApiError, decode } from './contract'
import type { Query, Schemas, SeriesPoint, TrafficApi, RunStatus, RunRequest } from '../types'

export type Scenario = 'default' | 'failed' | 'empty' | 'no-labels'
function sample<K extends keyof Schemas>(schema: K, index = 0): Schemas[K] {
  const entry = fixture.responses.filter(x => x.schema === schema)[index]
  if (!entry) throw new Error('Shared fixture example missing: ' + schema)
  return decode(schema, structuredClone(entry.body))
}

// UI-only adapter. All numeric values and labels come from the W0 fixture.
export function createMockApi(scenario: Scenario = 'default'): TrafficApi {
  let sequence = 0
  const progress = new Map<string, number>([['synthetic-run', 0]])
  const requests = new Map<string, RunRequest>()
  const known = (id: string) => {
    if (!progress.has(id) && !['synthetic-queued', 'synthetic-running', 'synthetic-succeeded', 'synthetic-failed', 'synthetic-empty'].includes(id)) throw new ApiError('NOT_FOUND', '找不到该合成任务。')
  }
  function page(id: string, query: Query, alarms = false) {
    known(id)
    const { start, end, page = 1, page_size = 100 } = query
    if (page < 1 || page_size < 1 || page_size > 1000 || (start && (!/^\d{4}-\d\d-\d\dT\d\d:\d\d:00Z$/.test(start) || !Number.isFinite(Date.parse(start)))) || (end && (!/^\d{4}-\d\d-\d\dT\d\d:\d\d:00Z$/.test(end) || !Number.isFinite(Date.parse(end)))) || (start && end && start >= end)) throw new ApiError('VALIDATION_ERROR', '请输入有效的 UTC 整分钟范围，结束时间须晚于开始。')
    const source = sample('SeriesPage')
    const items = scenario === 'empty' || id === 'synthetic-empty' ? [] : source.items.filter(p => (!start || p.timestamp >= start) && (!end || p.timestamp < end) && (!alarms || p.alarm === true))
    return decode('SeriesPage', { ...source, run_id: id, items: items.slice((page - 1) * page_size, page * page_size), total: items.length, page, page_size })
  }
  return {
    datasets: async () => sample('DatasetList'),
    submit: async input => {
      const request = decode('RunRequest', input)
      const dataset = sample('DatasetList').items[0]!
      if (request.method !== fixture.request.method) throw new ApiError('VALIDATION_ERROR', '统一样例仅提供隔离森林手工分数，不提供 AE 模型结果。')
      if (request.dataset_id !== dataset.dataset_id || !dataset.split_ids.includes(request.split_id) || !dataset.config_ids.includes(request.config_id)) throw new ApiError('VALIDATION_ERROR', '请选择已登记的数据、划分与配置。')
      if ([...progress.values()].some(n => n === 1 || n === 2)) throw new ApiError('RUN_BUSY', '已有活动合成任务，请等待结束。')
      const run_id = 'synthetic-session-' + ++sequence
      progress.set(run_id, 0); requests.set(run_id, request)
      return decode('RunAccepted', { run_id, status: 'queued' })
    },
    status: async id => {
      known(id)
      const fixed = ['synthetic-queued', 'synthetic-running', 'synthetic-succeeded', 'synthetic-failed'].indexOf(id)
      const step = fixed >= 0 ? fixed : Math.min(progress.get(id) ?? 0, 2)
      if (fixed < 0) progress.set(id, step + 1)
      const index = step === 2 && scenario === 'failed' ? 3 : step
      const status = sample('RunStatus', index)
      const request = requests.get(id)
      return decode('RunStatus', { ...status, run_id: id, config: { ...status.config, ...(request ? { dataset_id: request.dataset_id, split_id: request.split_id, method: request.method } : {}) } })
    },
    series: async (id, query) => page(id, query),
    alarms: async (id, query) => page(id, query, true),
    evaluation: async id => { known(id); return { ...sample('Evaluation', scenario === 'no-labels' ? 1 : 0), run_id: id } },
    minute: async (id, timestamp) => {
      known(id)
      const point = sample('SeriesPage').items.find(p => p.timestamp === timestamp)
      if (!point) throw new ApiError('NOT_FOUND', '该分钟不存在。')
      const detail = fixture.responses.filter(x => x.schema === 'MinuteDetail').map(x => decode('MinuteDetail', x.body)).find(x => x.point.timestamp === timestamp)
      if (detail) return { ...structuredClone(detail), run_id: id, labels: scenario === 'no-labels' ? null : detail.labels }
      const index = fixture.core_sample.timestamps.indexOf(timestamp)
      const labels = Object.fromEntries(Object.entries(fixture.core_sample.labels).map(([name, values]) => [name, values[index]!]))
      return decode('MinuteDetail', { ...sample('MinuteDetail'), run_id: id, point, current: null, history_residual: null, reconstruction_error_current: null, reconstruction_error_history: null, labels: scenario === 'no-labels' ? null : labels })
    },
    download: async (id, kind) => {
      known(id)
      if (kind === 'scores') throw new ApiError('EXECUTION_FAILED', '合成样例未提供 Parquet 文件；完整分数导出等待真实接口。')
      const value = kind === 'metrics' ? { ...sample('Evaluation', scenario === 'no-labels' ? 1 : 0), run_id: id } : sample('RunSummary').config
      return new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' })
    },
  }
}
