import type { EChartsOption } from 'echarts'

export function formatRate(value: string | null): string {
  return value === null ? '暂无数据' : `${(Number(value) * 100).toFixed(1)}%`
}

function chartTheme() {
  const tokens = getComputedStyle(document.documentElement)
  return {
    primary: tokens.getPropertyValue('--color-primary').trim(),
    muted: tokens.getPropertyValue('--color-muted').trim(),
    border: tokens.getPropertyValue('--color-border').trim(),
  }
}

export function barOption(
  labels: string[],
  values: number[],
  percent = false,
  horizontal = false,
): EChartsOption {
  const theme = chartTheme()
  const categories = {
    type: 'category' as const,
    data: labels,
    axisLine: { lineStyle: { color: theme.border } },
    axisLabel: { color: theme.muted, width: horizontal ? 90 : 70, overflow: 'truncate' as const },
  }
  const measure = {
    type: 'value' as const,
    min: 0,
    max: percent ? 100 : undefined,
    minInterval: percent ? undefined : 1,
    axisLabel: { color: theme.muted, formatter: percent ? '{value}%' : '{value}' },
    splitLine: { lineStyle: { color: theme.border, type: 'dashed' as const } },
  }
  return {
    color: [theme.primary],
    animationDuration: 300,
    aria: { enabled: true },
    tooltip: { trigger: 'axis', renderMode: 'richText', confine: true },
    grid: { left: horizontal ? 100 : 44, right: 24, top: 24, bottom: 48 },
    xAxis: horizontal ? measure : categories,
    yAxis: horizontal ? categories : measure,
    series: [
      {
        type: 'bar',
        data: values,
        barMaxWidth: 42,
        itemStyle: { borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] },
        label: {
          show: true,
          position: horizontal ? 'right' : 'top',
          color: theme.muted,
          formatter: percent ? '{c}%' : '{c}',
        },
      },
    ],
  }
}

export function trendOption(labels: string[], values: number[], titles: string[]): EChartsOption {
  const theme = chartTheme()
  return {
    color: [theme.primary],
    animationDuration: 300,
    tooltip: {
      trigger: 'axis',
      renderMode: 'richText',
      confine: true,
      formatter: (parameters) => {
        const point = Array.isArray(parameters) ? parameters[0] : parameters
        if (!point) return ''
        const title = (titles[point.dataIndex] ?? point.name).replace(/(.{18})/gu, '$1\n')
        return `${title}\n${point.name} · ${Number(point.value).toFixed(1)}%`
      },
      textStyle: { width: 220, lineHeight: 20 },
    },
    grid: { left: 48, right: 24, top: 32, bottom: 48 },
    xAxis: {
      type: 'category',
      data: labels,
      boundaryGap: true,
      axisLine: { lineStyle: { color: theme.border } },
      axisLabel: { color: theme.muted, width: 80, overflow: 'truncate' },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { color: theme.muted, formatter: '{value}%' },
      splitLine: { lineStyle: { color: theme.border, type: 'dashed' } },
    },
    series: [
      {
        name: '最终得分率',
        type: 'line',
        data: values,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { width: 2 },
        label: {
          show: values.length <= 6,
          position: 'top',
          color: theme.primary,
          formatter: '{c}%',
        },
      },
    ],
  }
}
