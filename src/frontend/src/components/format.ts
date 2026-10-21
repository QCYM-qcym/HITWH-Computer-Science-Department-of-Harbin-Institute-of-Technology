export const number = (value: number | null | undefined) => value == null ? '未提供' : value.toLocaleString('zh-CN', { maximumFractionDigits: 5 })
export const percent = (value: number | null | undefined) => value == null ? '不可评价' : (value * 100).toFixed(1) + '%'
export const time = (value: string | null | undefined) => value ? value.replace('T', ' ').replace('Z', ' UTC') : '—'
export const statusName = { queued: '排队中', running: '运行中', succeeded: '已完成', failed: '失败' }
export const methodName = { iforest: '隔离森林', current_ae: '当前特征 AE', history_ae: '历史增强 AE' }
export const reasonName: Record<string, string> = { warmup: '历史预热', gap: '时间缺口', invalid_input: '无效输入', not_common: '非共同分钟', nonfinite_score: '分数非有限' }
