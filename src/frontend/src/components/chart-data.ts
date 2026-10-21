import type { SeriesPoint } from '../types'
export function chartData(points: SeriesPoint[], budget = 300) {
  const chosen = new Set<number>()
  const stride = Math.max(1, Math.ceil(points.length / Math.max(2, budget)))
  points.forEach((p, i) => {
    if (i % stride === 0 || i === points.length - 1 || p.alarm || !p.valid || p.flow_count === null || points[i - 1]?.valid === false || points[i + 1]?.valid === false) chosen.add(i)
  })
  // Preserve both sides of real missing time and insert an explicit chart break.
  points.forEach((p, i) => { if (i && Date.parse(p.timestamp) - Date.parse(points[i - 1]!.timestamp) > 60000) { chosen.add(i - 1); chosen.add(i) } })
  const score: [string, number | null][] = [], threshold: [string, number | null][] = [], flow: [string, number | null][] = [], alarms: [string, number][] = []
  for (const i of [...chosen].sort((a, b) => a - b)) {
    const p = points[i]!, previous = points[i - 1]
    if (previous && Date.parse(p.timestamp) - Date.parse(previous.timestamp) > 60000) {
      const time = new Date(Date.parse(previous.timestamp) + 60000).toISOString()
      score.push([time, null]); threshold.push([time, null]); flow.push([time, null])
    }
    score.push([p.timestamp, p.valid ? p.score : null]); threshold.push([p.timestamp, p.valid ? p.threshold : null]); flow.push([p.timestamp, p.flow_count])
    if (p.alarm === true && p.score !== null) alarms.push([p.timestamp, p.score])
  }
  return { score, threshold, flow, alarms }
}
