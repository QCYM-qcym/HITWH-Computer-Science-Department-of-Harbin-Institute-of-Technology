<script setup lang="ts">
import { useWorkspaceStore } from '../stores/workspace'
import { time } from '../components/format'
const store = useWorkspaceStore()
defineEmits<{ navigate: [page: 'tasks'] }>()
</script>
<template>
  <div class="section-heading"><div><span class="eyebrow">DATA REGISTRY</span><h2>先确认数据，再开始检测</h2><p>仅使用已登记的数据版本、时间划分与配置。</p></div><button class="secondary" @click="store.initialize">刷新登记表 ↻</button></div>
  <div v-if="!store.datasets.length" class="empty panel">暂无已登记数据，请检查服务连接或刷新登记表。</div>
  <article v-for="dataset in store.datasets" :key="dataset.dataset_id" class="panel dataset-card">
    <div class="dataset-top"><div class="dataset-icon">▦</div><div><h3>{{ dataset.dataset_id }}</h3><p class="mono">{{ dataset.version }}</p></div><span class="badge" :class="dataset.available ? 'succeeded' : 'failed'">{{ dataset.available ? '可用' : '不可用' }}</span></div>
    <div class="dataset-facts"><div><small>特征维度</small><strong>{{ dataset.feature_count }} <span>维 / 分钟</span></strong></div><div><small>数据身份</small><strong class="small-value">{{ dataset.evidence_kind }}</strong></div><div><small>时间范围 · [起点，终点)</small><strong class="small-value">{{ time(dataset.time_range?.start) }}<br>至 {{ time(dataset.time_range?.end) }}</strong></div></div>
    <div class="dataset-footer"><div><span class="tag">划分 {{ dataset.split_ids.join(' / ') }}</span><span class="tag">配置 {{ dataset.config_ids.join(' / ') }}</span></div><button :disabled="!dataset.available" @click="store.selectedDatasetId = dataset.dataset_id; $emit('navigate', 'tasks')">创建检测任务 <span>↗</span></button></div>
    <p v-if="!dataset.available" class="error-text">{{ dataset.unavailable_reason }}</p>
  </article>
  <div class="note-grid"><article class="note-card"><span class="step-number">01</span><h3>时间边界清楚</h3><p>所有查询使用 UTC 整分钟；起点包含，终点不包含。缺测与预热分钟保留在时间轴上。</p></article><article class="note-card"><span class="step-number">02</span><h3>标签独立核查</h3><p>标签用于事后评价。页面只显示保存的结果，不计算检测分数或研究指标。</p></article><article class="note-card"><span class="step-number">03</span><h3>每次运行可追查</h3><p>通过任务编号查看状态、配置和结果。真实数据、模型与接口联调等待后续交付。</p></article></div>
</template>
