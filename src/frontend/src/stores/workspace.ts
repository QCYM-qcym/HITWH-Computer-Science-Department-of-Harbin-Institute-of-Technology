import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { createMockApi, type Scenario } from '../api/mock'
import { createHttpApi } from '../api/http'
import { followRun } from '../api/polling'
import { publicError } from '../api/contract'
import type { DatasetList, Evaluation, MinuteDetail, Query, RunRequest, RunStatus, SeriesPage, TrafficApi, ExportKind } from '../types'

export const useWorkspaceStore = defineStore('workspace', () => {
  const mode = import.meta.env.VITE_API_MODE === 'http' ? 'http' : 'mock'
  let api: TrafficApi = mode === 'http' ? createHttpApi() : createMockApi()
  const datasets = ref<DatasetList['items']>([])
  const selectedDatasetId = ref('')
  const acceptedRunIds = ref<string[]>([])
  const activeRun = ref<RunStatus | null>(null)
  const runs = ref<RunStatus[]>([])
  const series = ref<SeriesPage | null>(null)
  const alarms = ref<SeriesPage | null>(null)
  const evaluation = ref<Evaluation | null>(null)
  const minute = ref<MinuteDetail | null>(null)
  const comparisons = ref<{ run: RunStatus; evaluation: Evaluation }[]>([])
  const error = ref(''), tracking = ref(false), loading = ref(false), submitting = ref(false)
  const query = ref<Query>({ page: 1, page_size: 100 })
  const alarmPage = ref(1)
  const busy = computed(() => submitting.value || activeRun.value?.status === 'queued' || activeRun.value?.status === 'running')
  let stop: (() => void) | undefined
  let generation = 0, resultGeneration = 0, minuteGeneration = 0
  const clearResults = () => { series.value = null; alarms.value = null; evaluation.value = null; minute.value = null; loading.value = false; resultGeneration++; minuteGeneration++ }
  function stopTracking() { stop?.(); stop = undefined; tracking.value = false; generation++ }
  function setApi(value: TrafficApi) { stopTracking(); clearResults(); api = value }
  async function initialize() {
    error.value = ''
    try { datasets.value = (await api.datasets()).items } catch (e) { error.value = publicError(e) }
  }
  async function loadResults() {
    const id = activeRun.value?.run_id
    if (!id || activeRun.value?.status !== 'succeeded') return
    const version = ++resultGeneration
    loading.value = true; error.value = ''
    try {
      const [s, a, e] = await Promise.all([api.series(id, query.value), api.alarms(id, { ...query.value, page: alarmPage.value }), api.evaluation(id)])
      if (version !== resultGeneration || activeRun.value?.run_id !== id) return
      series.value = s; alarms.value = a; evaluation.value = e
    } catch (e) { if (version === resultGeneration) { series.value = null; alarms.value = null; evaluation.value = null; error.value = publicError(e) } }
    finally { if (version === resultGeneration) loading.value = false }
  }
  function follow(id: string) {
    stopTracking(); clearResults(); error.value = ''; activeRun.value = null; tracking.value = true
    const version = generation
    stop = followRun(api, id, {
      onStatus: status => {
        if (version !== generation) return
        activeRun.value = status
        runs.value = [status, ...runs.value.filter(x => x.run_id !== status.run_id)]
        if (status.status === 'succeeded' || status.status === 'failed') {
          tracking.value = false
          if (status.status === 'succeeded') void loadResults()
        }
      },
      onError: e => { if (version === generation) { tracking.value = false; error.value = publicError(e) } },
    })
  }
  async function submit(request: RunRequest) {
    submitting.value = true; error.value = ''
    try { const accepted = await api.submit(request); acceptedRunIds.value.push(accepted.run_id); follow(accepted.run_id) }
    catch (e) { error.value = publicError(e) }
    finally { submitting.value = false }
  }
  async function openRun(id: string) {
    stopTracking(); clearResults(); error.value = ''; activeRun.value = null
    const version = generation
    try {
      const status = await api.status(id)
      if (version !== generation) return
      activeRun.value = status
      runs.value = [status, ...runs.value.filter(x => x.run_id !== id)]
      if (status.status === 'queued' || status.status === 'running') follow(id)
      else if (status.status === 'succeeded') await loadResults()
    } catch (e) { if (version === generation) error.value = publicError(e) }
  }
  async function selectMinute(timestamp: string) {
    const id = activeRun.value?.run_id
    if (!id) return
    const version = ++minuteGeneration; minute.value = null; error.value = ''
    try { const value = await api.minute(id, timestamp); if (version === minuteGeneration && activeRun.value?.run_id === id) minute.value = value }
    catch (e) { if (version === minuteGeneration) error.value = publicError(e) }
  }
  async function compare(id: string) {
    error.value = ''
    try {
      const run = await api.status(id)
      if (run.status !== 'succeeded') { error.value = '只可添加已完成的任务。'; return }
      const e = await api.evaluation(id)
      comparisons.value = [...comparisons.value.filter(x => x.run.run_id !== id), { run, evaluation: e }]
    } catch (e) { error.value = publicError(e) }
  }
  async function download(kind: ExportKind) {
    if (!activeRun.value || activeRun.value.status !== 'succeeded') return
    const id = activeRun.value.run_id
    try {
      const blob = await api.download(id, kind)
      const url = URL.createObjectURL(blob), link = document.createElement('a')
      link.href = url; link.download = `${id}-${kind}.${kind === 'scores' ? 'parquet' : 'json'}`; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) { error.value = publicError(e) }
  }
  async function changeScenario(scenario: Scenario) {
    setApi(createMockApi(scenario)); activeRun.value = null; runs.value = []; acceptedRunIds.value = []; comparisons.value = []; query.value = { page: 1, page_size: 100 }; alarmPage.value = 1
    await initialize()
  }
  return { mode, datasets, selectedDatasetId, acceptedRunIds, activeRun, runs, series, alarms, evaluation, minute, comparisons, error, tracking, loading, submitting, query, alarmPage, busy, setApi, initialize, submit, openRun, stopTracking, loadResults, selectMinute, compare, download, changeScenario }
})
