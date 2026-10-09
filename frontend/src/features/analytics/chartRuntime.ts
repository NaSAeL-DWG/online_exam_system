import { init, use } from 'echarts/core'
import { AriaComponent, GridComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

// 共用运行时只注册坐标、提示与渲染器；教师柱图无需同时下载学生趋势的折线图代码。
use([GridComponent, TooltipComponent, AriaComponent, SVGRenderer])

export async function registerChart(kind: 'bar' | 'line'): Promise<void> {
  if (kind === 'line') await import('./lineChart')
  else await import('./barChart')
}

export function createChart(element: HTMLElement) {
  return init(element, undefined, { renderer: 'svg' })
}
