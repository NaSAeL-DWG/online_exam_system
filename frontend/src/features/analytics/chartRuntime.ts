import { init, use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { AriaComponent, GridComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

// 仅注册本轮使用的图形；此模块通过动态导入加载，不进入工作台与考试作答主包。
use([BarChart, LineChart, GridComponent, TooltipComponent, AriaComponent, SVGRenderer])

export function createChart(element: HTMLElement) {
  return init(element, undefined, { renderer: 'svg' })
}
