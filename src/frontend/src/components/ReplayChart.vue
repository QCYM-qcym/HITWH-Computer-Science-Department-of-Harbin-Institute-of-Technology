<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import type { SeriesPoint } from '../types'
import { chartData } from './chart-data'
echarts.use([LineChart, ScatterChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, SVGRenderer])
const props = defineProps<{ points: SeriesPoint[]; budget: number }>()
const emit = defineEmits<{ select: [timestamp: string] }>()
const element = ref<HTMLDivElement>()
let chart: echarts.ECharts | undefined, observer: ResizeObserver | undefined
function draw() {
  if (!element.value || !element.value.clientWidth) return
  chart ??= echarts.init(element.value, undefined, { renderer: 'svg' })
  const data = chartData(props.points, props.budget)
  const axis = { type: 'time', minInterval: 60000, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false }, axisLabel: { color: '#71817b', formatter: (value: number) => new Date(value).toISOString().slice(11, 16) } }
  chart.setOption({
    animation: false, useUTC: true, color: ['#20877c', '#536dd0', '#acada6', '#da725b'],
    tooltip: { trigger: 'axis', confine: true, renderMode: 'richText' },
    legend: { top: 0, right: 0, icon: 'roundRect', itemWidth: 13, itemHeight: 4, textStyle: { color: '#60716b', fontSize: 11 } },
    grid: [{ left: 50, right: 24, top: 45, height: '29%' }, { left: 50, right: 24, top: '57%', height: '29%' }],
    xAxis: [{ ...axis, gridIndex: 0 }, { ...axis, gridIndex: 1 }],
    yAxis: [{ type: 'value', name: '流记录数', nameTextStyle: { color: '#71817b' }, splitLine: { lineStyle: { color: '#edf0ed' } } }, { type: 'value', name: '异常分数', gridIndex: 1, nameTextStyle: { color: '#71817b' }, splitLine: { lineStyle: { color: '#edf0ed' } } }],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1] }, { type: 'slider', xAxisIndex: [0, 1], bottom: 0, height: 15, borderColor: '#edf0ed' }],
    series: [
      { name: '流量', type: 'line', data: data.flow, connectNulls: false, symbolSize: 6, lineStyle: { width: 2 }, areaStyle: { opacity: 0.06 } },
      { name: '异常分数', type: 'line', data: data.score, xAxisIndex: 1, yAxisIndex: 1, connectNulls: false, symbolSize: 6, lineStyle: { width: 2 } },
      { name: '阈值', type: 'line', data: data.threshold, xAxisIndex: 1, yAxisIndex: 1, connectNulls: false, symbol: 'none', lineStyle: { type: 'dashed', width: 1.4 } },
      { name: '报警', type: 'scatter', data: data.alarms, xAxisIndex: 1, yAxisIndex: 1, symbolSize: 10, z: 10, itemStyle: { color: '#da725b', borderColor: '#fff', borderWidth: 2 } },
    ],
  }, true)
  chart.off('click')
  chart.on('click', params => { const value = params.value; if (Array.isArray(value) && typeof value[0] === 'string') emit('select', value[0]) })
}
watch(() => [props.points, props.budget], draw, { deep: true })
onMounted(() => { draw(); if (typeof ResizeObserver !== 'undefined' && element.value) { observer = new ResizeObserver(() => { draw(); chart?.resize() }); observer.observe(element.value) } })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>
<template><div ref="element" class="replay-chart" role="img" aria-label="按 UTC 对齐的流量与异常分数曲线；缺失值保留断点，完整分钟可在下方表格查看"></div></template>
