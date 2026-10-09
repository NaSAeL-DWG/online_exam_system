import type { APIResponse, Page, Route } from '@playwright/test'

/** 缓冲真实服务端响应，仅延迟网络交付，不改变业务状态或响应正文。 */
export async function delayNextResponse(page: Page, pathname: string) {
  let resolveReady!: (response: APIResponse) => void
  let rejectReady!: (error: unknown) => void
  const ready = new Promise<APIResponse>((resolve, reject) => {
    resolveReady = resolve
    rejectReady = reject
  })
  // 测试失败时也释放路由；ready 的真实错误仍在调用方 await 时传播。
  void ready.catch(() => undefined)
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  let resolveDelivered!: () => void
  const delivered = new Promise<void>((resolve) => {
    resolveDelivered = resolve
  })
  let first = true
  let deliveryError: unknown
  const handler = async (route: Route) => {
    if (!first || route.request().method() !== 'GET') {
      await route.continue()
      return
    }
    first = false
    try {
      const response = await route.fetch()
      await response.body()
      resolveReady(response)
      await gate
      await route.fulfill({ response })
    } catch (error) {
      deliveryError = error
      rejectReady(error)
    } finally {
      resolveDelivered()
    }
  }
  await page.route(`**${pathname}`, handler)
  return {
    ready,
    release,
    async deliver() {
      release()
      await delivered
      if (deliveryError) throw deliveryError
    },
  }
}

/** 控制浏览器窗口焦点边界，页面按产品约定重新读取当前授权结果。 */
export async function refreshOnFocus(page: Page) {
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
}

/** 等待交付后的浏览器绘制，断言已处理旧响应后实际可见的页面。 */
export async function nextPaint(page: Page) {
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
      }),
  )
}
