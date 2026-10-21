<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useWorkspaceStore } from './stores/workspace'
import DataView from './views/DataView.vue'
import TasksView from './views/TasksView.vue'
import AnalysisView from './views/AnalysisView.vue'
import ComparisonView from './views/ComparisonView.vue'
import type { Scenario } from './api/mock'
const store = useWorkspaceStore()
type Page = 'data' | 'tasks' | 'analysis' | 'comparison'
const page = ref<Page>('data'), scenario = ref<Scenario>('default')
const pages = [{ id: 'data', icon: '▦', label: '数据查看', sub: 'Data registry' }, { id: 'tasks', icon: '⊞', label: '检测任务', sub: 'Detection runs' }, { id: 'analysis', icon: '⌁', label: '异常分析', sub: 'Minute replay' }, { id: 'comparison', icon: '≋', label: '实验对比', sub: 'Experiment review' }] as const
const currentPage = computed(() => pages.find(x => x.id === page.value)!)
watch(page, () => { if (window.scrollY > 0) window.scrollTo(0, 0) })
onMounted(store.initialize)
onBeforeUnmount(store.stopTracking)
function changeScenario(event: Event) { scenario.value = (event.target as HTMLSelectElement).value as Scenario; void store.changeScenario(scenario.value) }
</script>
<template>
  <div class="app-shell"><aside class="sidebar"><a class="brand" href="#" @click.prevent="page = 'data'"><span class="brand-mark"><i></i><i></i><i></i><i></i></span><span>流量观测台<small>TRAFFIC OBSERVATORY</small></span></a><div class="sidebar-label">工作空间 / WORKSPACE</div><nav aria-label="主导航"><button v-for="p in pages" :key="p.id" :data-nav="p.id" :class="['nav-item', { active: page === p.id }]" :aria-current="page === p.id ? 'page' : undefined" @click="page = p.id"><span class="nav-icon">{{ p.icon }}</span><span>{{ p.label }}<small>{{ p.sub }}</small></span><span v-if="page === p.id" class="nav-arrow">↗</span></button></nav><div class="sidebar-note"><span class="dot"></span> 本地离线检测<p>分钟级观测<br>时间感知 · 可追溯</p><small>W3 / FRONTEND · v0.1</small></div></aside>
  <main><header class="topbar"><span>研究工作空间 <span class="slash">/</span> <strong>{{ currentPage.label }}</strong></span><span class="topbar-right"><span class="dot"></span> {{ store.mode === 'mock' ? '合成样例' : 'HTTP 接口' }}<span class="tag">CONTRACT v1.0</span></span></header>
    <div class="content"><div class="page-title"><div><span class="eyebrow">TIME-AWARE TRAFFIC ANALYSIS</span><h1>{{ currentPage.label }}<span class="title-dot">.</span></h1></div><span class="page-index">0{{ pages.findIndex(x => x.id === page) + 1 }} <span>/ 04</span></span></div>
    <div :class="['evidence-banner', { real: store.mode === 'http' }]"><div><strong>{{ store.mode === 'mock' ? 'SYNTHETIC_ONLY · 合成演示' : 'HTTP 模式 · 请核对每个任务的数据身份' }}</strong><p>{{ store.mode === 'mock' ? '统一四分钟手工样例，用于核查页面行为，不代表模型输出或实验结果。' : '已切换契约 v1 客户端。实际联调状态请以交付记录为准。' }}</p></div><label v-if="store.mode === 'mock'" class="scenario-select">核查场景<select :value="scenario" @change="changeScenario"><option value="default">统一样例</option><option value="failed">任务失败</option><option value="empty">空查询结果</option><option value="no-labels">标签缺失</option></select></label></div>
    <p v-if="store.activeRun" class="run-context mono">RUN {{ store.activeRun.run_id }} <span class="tag">{{ store.activeRun.evidence_kind }}</span></p>
    <div v-if="store.error" role="alert" class="global-error"><strong>操作未完成</strong><span>{{ store.error }}</span><button class="text-button" aria-label="关闭错误提示" @click="store.error = ''">×</button></div>
    <DataView v-if="page === 'data'" @navigate="page = $event"/><TasksView v-else-if="page === 'tasks'" @navigate="page = $event"/><AnalysisView v-else-if="page === 'analysis'" @navigate="page = $event"/><ComparisonView v-else/>
    <footer><span>面向动态网络环境的时间感知流量异常检测</span><span>UTC 时间基准 · 标签独立评价</span></footer></div>
  </main></div>
</template>
