import { describe, expect, it } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMockApi } from '../api/mock'
import { useWorkspaceStore } from '../stores/workspace'
import { chartData } from '../components/chart-data'
import App from '../App.vue'

describe('replay and evaluation UI', () => {
  it('shows zero-normal FPR as unavailable with its denominator reason, never zero percent', async () => {
    const api = createMockApi(), original = api.evaluation
    api.evaluation = async id => ({ ...await original(id),
      normal_coverage: { eligible: 0, total: 0 },
      metrics: { tp: 0, fp: 0, tn: 0, fn: 1, precision: null,
        recall: 0, f1: 0, fpr: null, undefined_reasons: ['precision', 'fpr'] },
    })
    const pinia = createPinia(), store = useWorkspaceStore(pinia); store.setApi(api)
    const wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises(); await store.openRun('synthetic-succeeded'); await flushPromises()
    await wrapper.get('[data-nav="comparison"]').trigger('click')
    const card = wrapper.findAll('.metric-strip article').find(x => x.text().includes('正常误报率'))!
    expect(card.text()).toContain('不可评价')
    expect(card.text()).not.toContain('0.0%')
    expect(wrapper.text()).toContain('precision、fpr')
    expect(store.evaluation?.metrics?.fpr).toBeNull()
    wrapper.unmount()
  })
  it('keeps warmup / missing time as gaps and preserves alarms while sampling', async () => {
    const page = await createMockApi().series('synthetic-run', {})
    const data = chartData(page.items, 2)
    expect(data.score[0]).toEqual(['2026-01-01T00:00:00Z', null])
    expect(data.alarms).toEqual([['2026-01-01T00:02:00Z', 1.5]])
    const missing = chartData([page.items[1]!, page.items[3]!])
    expect(missing.score).toContainEqual(['2026-01-01T00:02:00.000Z', null])
    expect(page.items[0]?.score).toBeNull()
  })
  it('locates the whole unalarmed attack episode at its unscored start without inventing a score', async () => {
    const pinia = createPinia()
    const store = useWorkspaceStore(pinia)
    store.setApi(createMockApi())
    const wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises()
    await store.openRun('synthetic-succeeded')
    await flushPromises()
    await wrapper.get('[data-nav="analysis"]').trigger('click')
    const evaluationBefore = JSON.stringify(store.evaluation)
    await wrapper.get('[data-test="missed-attack"]').trigger('click')
    await flushPromises()
    expect(store.minute?.point.timestamp).toBe('2026-01-01T00:00:00Z')
    expect(store.evaluation?.intervals.find(x => x.kind === 'missed_attack')).toMatchObject({
      start: '2026-01-01T00:00:00Z', end: '2026-01-01T00:02:00Z', minute_count: 2,
    })
    expect(store.minute?.point).toMatchObject({ valid: false, score: null, threshold: null, alarm: null, invalid_reason: 'warmup', flow_count: null })
    expect(store.minute?.current).toBeNull()
    expect(store.minute?.history_residual).toBeNull()
    expect(store.minute?.reconstruction_error_current).toBeNull()
    expect(store.minute?.reconstruction_error_history).toBeNull()
    expect(store.minute?.labels).toEqual({ dos: 1, scan11: 0, scan44: 0, botnet: 0, blacklist: 0, udpscan: 0, sshscan: 0, spam: 0 })
    expect(JSON.stringify(store.evaluation)).toBe(evaluationBefore)
    expect(store.evaluation?.metrics?.fn).toBe(1)
    expect(store.evaluation?.excluded_attack_minutes).toBe(1)
    expect(wrapper.text()).toContain('当前特征')
    expect(wrapper.text()).toContain('历史偏离')
    expect(wrapper.text()).toContain('重构误差')
    expect(wrapper.text()).toContain('未提供')
    expect(wrapper.text()).toContain('SYNTHETIC_ONLY')
    wrapper.unmount()
  })
  it('explains whole label episodes separately from scored FN and keeps partial-hit metrics pointwise', async () => {
    const pinia = createPinia(), store = useWorkspaceStore(pinia); store.setApi(createMockApi())
    const wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises(); await store.openRun('synthetic-succeeded'); await flushPromises()
    await wrapper.get('[data-nav="analysis"]').trigger('click')
    const panel = wrapper.get('.missed-panel')
    expect(panel.get('h3').text()).toBe('未报警攻击片段')
    expect(panel.text()).toContain('原始攻击标签')
    expect(panel.text()).toContain('整个攻击片段没有有效报警')
    expect(panel.text()).toContain('不可评分分钟')
    expect(panel.text()).toContain('片段长度不等于漏报数（FN）')
    expect(panel.text()).toContain('部分命中')
    expect(panel.text()).toContain('不会把其余分钟改判为命中')
    expect(store.evaluation?.metrics).toMatchObject({ tp: 0, fp: 1, tn: 1, fn: 1 })
    wrapper.unmount()
  })
  it('explicitly identifies the selected invalid minute while retaining null score and channels', async () => {
    const pinia = createPinia(), store = useWorkspaceStore(pinia); store.setApi(createMockApi())
    const wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises(); await store.openRun('synthetic-succeeded')
    await store.selectMinute('2026-01-01T00:00:00Z'); await flushPromises()
    await wrapper.get('[data-nav="analysis"]').trigger('click')
    const notice = wrapper.get('[data-test="minute-unscored"]')
    expect(notice.text()).toContain('该分钟不可评分')
    expect(notice.text()).toContain('历史预热')
    expect(notice.text()).toContain('分数、阈值与报警均未提供')
    expect(store.minute?.point).toMatchObject({ timestamp: '2026-01-01T00:00:00Z', valid: false, score: null, threshold: null, alarm: null, invalid_reason: 'warmup', flow_count: null })
    expect(store.minute?.current).toBeNull()
    expect(store.minute?.history_residual).toBeNull()
    expect(store.minute?.reconstruction_error_current).toBeNull()
    expect(store.minute?.reconstruction_error_history).toBeNull()
    expect(store.minute?.labels).toEqual({ dos: 1, scan11: 0, scan44: 0, botnet: 0, blacklist: 0, udpscan: 0, sshscan: 0, spam: 0 })
    expect(wrapper.get('.feature-table tbody tr').findAll('td').slice(1).map(x => x.text())).toEqual(['未提供', '未提供', '未提供', '未提供'])
    expect(store.minute?.labels).not.toBeNull()
    wrapper.unmount()
  })
  it('keeps server metrics unchanged by display limits and provides an empty / no-alarm state', async () => {
    const pinia = createPinia()
    const store = useWorkspaceStore(pinia)
    store.setApi(createMockApi('empty'))
    const wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises(); await store.openRun('synthetic-succeeded'); await flushPromises()
    await wrapper.get('[data-nav="analysis"]').trigger('click')
    expect(wrapper.text()).toContain('当前范围没有分钟记录')
    expect(wrapper.text()).toContain('没有报警记录')
    await wrapper.get('[data-nav="comparison"]').trigger('click')
    expect(wrapper.text()).toContain('50.0%')
    expect(store.evaluation?.metrics?.fpr).toBe(0.5)
    wrapper.unmount()
  })
  it('displays undefined metrics as unavailable, and long feature labels without dropping channels', async () => {
    const api = createMockApi('no-labels')
    const pinia = createPinia(); const store = useWorkspaceStore(pinia); store.setApi(api)
    const wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises(); await store.openRun('synthetic-succeeded'); await flushPromises()
    await wrapper.get('[data-nav="comparison"]').trigger('click')
    expect(wrapper.text()).toContain('No labels')
    expect(wrapper.text()).not.toContain('NaN')
    await wrapper.get('[data-nav="analysis"]').trigger('click')
    expect(wrapper.get('.missed-panel').text()).toContain('标签缺失')
    expect(wrapper.find('[data-test="missed-attack"]').exists()).toBe(false)
    wrapper.unmount()
  })
  it('shows an unalarmed normal minute without inventing missing channels or changing full evaluation', async () => {
    const api = createMockApi()
    const pinia = createPinia(); const store = useWorkspaceStore(pinia); store.setApi(api)
    const wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises(); await store.openRun('synthetic-succeeded')
    store.query = { start: '2026-01-01T00:03:00Z', end: '2026-01-01T00:04:00Z', page: 1, page_size: 100 }
    await store.loadResults(); await store.selectMinute('2026-01-01T00:03:00Z'); await flushPromises()
    await wrapper.get('[data-nav="analysis"]').trigger('click')
    expect(wrapper.text()).toContain('没有报警记录')
    expect(wrapper.text()).toContain('八标签均零 · 正常候选')
    expect(store.minute?.history_residual).toBeNull()
    expect(store.evaluation?.metrics?.fp).toBe(1)
    wrapper.unmount()
  })
  it('renders four independent channels and wraps a long feature name', async () => {
    const api = createMockApi(), original = api.minute
    api.minute = async (id, stamp) => {
      const detail = await original(id, stamp)
      return { ...detail, feature_names: ['long_feature_'.repeat(15), ...detail.feature_names.slice(1)], current: Array(134).fill(2), history_residual: Array(134).fill(-3), reconstruction_error_current: Array(134).fill(4), reconstruction_error_history: Array(134).fill(5) }
    }
    const pinia = createPinia(); const store = useWorkspaceStore(pinia); store.setApi(api)
    const wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises(); await store.openRun('synthetic-succeeded'); await store.selectMinute('2026-01-01T00:01:00Z'); await flushPromises()
    await wrapper.get('[data-nav="analysis"]').trigger('click')
    const cells = wrapper.get('.feature-table tbody tr').findAll('td')
    expect(cells.map(x => x.text())).toEqual(['long_feature_'.repeat(15), '2', '-3', '4', '5'])
    wrapper.unmount()
  })
  it('keeps an accepted run ID visible and retryable after the first status lookup fails', async () => {
    const api = createMockApi(), original = api.status
    api.status = async () => { throw new Error('transient offline') }
    const pinia = createPinia(); const store = useWorkspaceStore(pinia); store.setApi(api)
    const wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises(); await wrapper.get('[data-nav="tasks"]').trigger('click')
    await store.submit({ dataset_id: 'synthetic-v1', split_id: 'split-v1', method: 'iforest', config_id: 'smoke-v1' }); await flushPromises()
    expect(store.activeRun).toBeNull()
    expect(wrapper.text()).toContain('synthetic-session-1')
    api.status = async id => original(id === 'synthetic-session-1' ? 'synthetic-succeeded' : id).then(s => ({ ...s, run_id: id }))
    await wrapper.get('[data-test="retry-status"]').trigger('click'); await flushPromises()
    expect(store.activeRun?.run_id).toBe('synthetic-session-1')
    expect(store.activeRun?.status).toBe('succeeded')
    wrapper.unmount()
  })
  it('keeps the applied page size until Apply, then resets minute and alarm pagination', async () => {
    const api = createMockApi(), original = api.series
    const seen: { page?: number; page_size?: number }[] = []
    api.series = async (id, query) => { seen.push({ ...query }); return { ...await original(id, query), total: 1200 } }
    const pinia = createPinia(); const store = useWorkspaceStore(pinia); store.setApi(api)
    const wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises(); await store.openRun('synthetic-succeeded'); await wrapper.get('[data-nav="analysis"]').trigger('click')
    const sizeControl = wrapper.findAll('label').find(x => x.text().startsWith('每页分钟'))!.get('select')
    await sizeControl.setValue('500')
    await wrapper.get('.chart-panel .pagination').findAll('button')[1]!.trigger('click'); await flushPromises()
    expect(seen.at(-1)?.page).toBe(2)
    expect(seen.at(-1)?.page_size).toBe(100)
    store.alarmPage = 3
    await wrapper.get('.range-form').trigger('submit'); await flushPromises()
    expect(seen.at(-1)?.page).toBe(1)
    expect(seen.at(-1)?.page_size).toBe(500)
    expect(store.alarmPage).toBe(1)
    wrapper.unmount()
  })
  it('preselects the dataset whose Create action the user clicked', async () => {
    const api = createMockApi(), original = api.datasets
    api.datasets = async () => { const list = await original(); return { items: [...list.items, { ...list.items[0]!, dataset_id: 'synthetic-second' }] } }
    const pinia = createPinia(); const store = useWorkspaceStore(pinia); store.setApi(api)
    const wrapper = mount(App, { global: { plugins: [pinia] } })
    await flushPromises()
    await wrapper.findAll('button').filter(x => x.text().includes('创建检测任务'))[1]!.trigger('click')
    expect((wrapper.get('.form-grid select').element as HTMLSelectElement).value).toBe('synthetic-second')
    wrapper.unmount()
  })
})
