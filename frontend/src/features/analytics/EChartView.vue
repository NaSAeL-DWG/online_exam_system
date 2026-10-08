<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { EChartsOption } from 'echarts'
import type { EChartsType } from 'echarts/core'

const props = defineProps<{ option: EChartsOption; label: string }>()
const element = ref<HTMLDivElement | null>(null)
const failure = ref(false)
let chart: EChartsType | null = null
let observer: ResizeObserver | null = null
let disposed = false
function renderChart(): void {
  // ECharts 默认会重写容器的可访问名称，统一使用页面提供的明确图表标题。
  chart?.setOption(
    { ...props.option, aria: { enabled: true, label: { description: props.label } } },
    { notMerge: true },
  )
}

onMounted(async () => {
  try {
    const { createChart } = await import('./chartRuntime')
    if (disposed || !element.value) return
    chart = createChart(element.value)
    renderChart()
    observer = new ResizeObserver(() => chart?.resize())
    observer.observe(element.value)
  } catch {
    if (!disposed) failure.value = true
  }
})
watch(() => [props.option, props.label], renderChart)
onBeforeUnmount(() => {
  disposed = true
  observer?.disconnect()
  chart?.dispose()
  chart = null
})
</script>
<template>
  <div class="chart-shell">
    <div v-if="!failure" ref="element" class="analytics-chart" role="img" :aria-label="label" />
    <p v-else class="muted" role="status">图表暂不可显示，可查看下方数据。</p>
  </div>
</template>
<style scoped>
.chart-shell {
  min-width: 0;
  width: 100%;
}
.analytics-chart {
  height: 300px;
  width: 100%;
  min-width: 0;
}
</style>
