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
