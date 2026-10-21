import type { RunStatus, TrafficApi } from '../types'

export function followRun(api: TrafficApi, id: string, options: { onStatus: (status: RunStatus) => void; onError: (error: unknown) => void; interval?: number }) {
  const controller = new AbortController()
  let timer: ReturnType<typeof setTimeout> | undefined
  let stopped = false
  async function tick() {
    try {
      const status = await api.status(id, controller.signal)
      if (stopped) return
      options.onStatus(status)
      if (status.status === 'queued' || status.status === 'running') timer = setTimeout(tick, options.interval ?? 750)
    } catch (error) { if (!stopped) options.onError(error) }
  }
  void tick()
  return () => { stopped = true; controller.abort(); clearTimeout(timer) }
}
