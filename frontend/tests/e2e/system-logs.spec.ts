import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import { apiWrite, signedContext } from './grading-fixtures'

async function login(page: Page) {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
  await page.getByLabel('密码', { exact: true }).fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/home')
}

test('管理员从独立入口查看运行日志与操作审计', async ({ page }) => {
  await login(page)
  await page.getByRole('link', { name: '系统日志', exact: true }).click()
  await expect(page).toHaveURL('/admin/logs')
  await expect(page.getByRole('heading', { name: '系统日志', exact: true })).toBeVisible()
  await expect(page.getByLabel('自动刷新')).toBeChecked()
  await expect(page.getByLabel('自动滚动')).toBeChecked()
  await expect(
    page
      .locator('.field')
      .filter({ has: page.getByRole('combobox', { name: '日志等级', exact: true }) }),
  ).toContainText('INFO · 仅信息')
  await page.getByRole('tab', { name: '操作审计' }).click()
  await expect(page.getByLabel('操作者 ID')).toBeVisible()
  await expect(page.getByLabel('操作类型')).toBeVisible()
  await expect(page.getByLabel('对象类型')).toBeVisible()
})

test('运行记录来自真实接口且关键词筛选可重置', async ({ page }) => {
  await login(page)
  const response = await page.request.get('/api/admin/logs/runtime')
  expect(response.ok()).toBeTruthy()
  const body = await response.json()
  expect(body.items.length).toBeGreaterThan(0)
  await page.goto('/admin/logs')
  await expect(page.getByRole('region', { name: '日志记录' })).toContainText(body.items[0].message)
  await page.getByLabel('关键词', { exact: true }).fill('不存在的日志标记zzzz-no-result')
  await page.getByRole('button', { name: '应用筛选' }).click()
  await expect(page.getByText('当前筛选下暂无日志')).toBeVisible()
  await page.getByRole('button', { name: '重置筛选' }).click()
  await expect(page.locator('.log-entry').first()).toBeVisible()
})

test('全局文件和临时DEBUG设置持久可见，并可下载当前筛选', async ({ page, browser }) => {
  await login(page)
  const original = await (await page.request.get('/api/admin/logs/settings')).json()
  const module = `frontend-e2e-${Date.now()}`
  try {
    await page.goto('/admin/logs')
    await page.getByRole('button', { name: '采集设置' }).click()
    await expect(page.getByRole('checkbox', { name: '写入日志文件' })).toBeChecked({
      checked: original.file_enabled,
    })
    await page.getByRole('checkbox', { name: '写入日志文件' }).setChecked(!original.file_enabled)
    await expect
      .poll(
        async () =>
          (await (await page.request.get('/api/admin/logs/settings')).json()).file_enabled,
      )
      .toBe(!original.file_enabled)
    await page.getByLabel('DEBUG 模块').fill(module)
    await page.getByRole('button', { name: '开启 15 分钟' }).click()
    await expect(page.locator('.logs-debug-item').filter({ hasText: module })).toContainText(
      '到期自动关闭',
    )
    const otherContext = await browser.newContext({
      storageState: await page.context().storageState(),
    })
    const other = await otherContext.newPage()
    await other.goto(`${new URL(page.url()).origin}/admin/logs`)
    await other.getByRole('button', { name: '采集设置' }).click()
    await expect(other.locator('.logs-debug-item').filter({ hasText: module })).toBeVisible()
    await otherContext.close()
    await page
      .locator('.logs-debug-item')
      .filter({ hasText: module })
      .getByRole('button', { name: '提前关闭' })
      .click()
    await expect(page.locator('.logs-debug-item').filter({ hasText: module })).toHaveCount(0)
    await page.getByRole('button', { name: '关闭采集设置' }).click()
    await page.getByRole('tab', { name: '操作审计' }).click()
    await page.getByLabel('关键词', { exact: true }).fill(module)
    await page.getByRole('button', { name: '应用筛选' }).click()
    const downloadPromise = page.waitForEvent('download')
    const responsePromise = page.waitForResponse((response) =>
      response.url().includes('/audit/export'),
    )
    await page.getByRole('button', { name: '下载当前筛选' }).click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toMatch(/\.log$/)
    expect((await responsePromise).ok()).toBeTruthy()
    const contents = await readFile((await download.path())!, 'utf8')
    expect(contents).toContain(module)
    expect(contents).toContain('操作')
    expect(contents).not.toContain('\ufffd')
  } finally {
    await apiWrite(
      page.request,
      '/admin/logs/settings',
      { file_enabled: original.file_enabled },
      'PATCH',
    )
    await apiWrite(page.request, `/admin/logs/debug/${module}`, { enabled: false }, 'PUT')
  }
})

test('上翻暂停跟随并计数新记录，加载历史保持位置且增量不重复', async ({ page }) => {
  test.setTimeout(60_000)
  await login(page)
  const module = `scroll-e2e-${Date.now()}`
  for (let index = 0; index < 110; index += 1) {
    await apiWrite(page.request, `/admin/logs/debug/${module}`, { enabled: index % 2 === 0 }, 'PUT')
  }
  await expect
    .poll(
      async () => (await (await page.request.get('/api/admin/logs/runtime')).json()).items.length,
    )
    .toBe(100)
  await page.goto('/admin/logs')
  await expect(page.locator('.log-entry')).toHaveCount(100)
  const region = page.getByRole('region', { name: '日志记录' })
  await region.evaluate((element) => {
    element.scrollTop = 0
  })
  await expect(page.getByText('已暂停跟随，可安心翻阅历史')).toBeVisible()
  await apiWrite(page.request, `/admin/logs/debug/${module}`, { enabled: true }, 'PUT')
  await expect(page.getByRole('button', { name: /条新日志 · 回到最新/ })).toBeVisible({
    timeout: 10_000,
  })
  expect(await region.evaluate((element) => element.scrollTop)).toBeLessThan(3)
  await page.getByRole('button', { name: /条新日志 · 回到最新/ }).click()
  await expect(page.getByText('正在跟随最新记录')).toBeVisible()
  await page.getByLabel('自动刷新').uncheck()
  await region.evaluate((element) => {
    element.scrollTop = 0
  })
  const anchor = page.locator('.log-entry').first()
  const anchorId = await anchor.getAttribute('data-log-id')
  const before = (await anchor.boundingBox())!.y
  await page.getByRole('button', { name: '加载更早记录' }).click()
  await expect(page.locator('.log-entry')).not.toHaveCount(100)
  const preserved = page.locator(`.log-entry[data-log-id="${anchorId}"]`)
  expect(Math.abs((await preserved.boundingBox())!.y - before)).toBeLessThan(3)
  const ids = await page
    .locator('.log-entry')
    .evaluateAll((elements) => elements.map((element) => (element as HTMLElement).dataset.logId))
  expect(new Set(ids).size).toBe(ids.length)
  await apiWrite(page.request, `/admin/logs/debug/${module}`, { enabled: false }, 'PUT')
})

test('日志授权变为403后立即清空记录并停止轮询', async ({ page, browser }) => {
  await login(page)
  const loginName = `LOG403${Date.now()}`
  const password = 'Temporary123!'
  await apiWrite(page.request, '/admin/teachers', {
    teacher_no: loginName,
    real_name: '日志授权测试教师',
    email: `${loginName}@example.com`,
    phone_number: '13800000000',
    temporary_password: password,
  })
  const teacher = await signedContext(browser, new URL(page.url()).origin, loginName, password)
  await page.goto('/admin/logs')
  await expect(page.locator('.log-entry').first()).toBeVisible()
  await page.context().clearCookies()
  await page.context().addCookies(await teacher.cookies())
  await page.getByRole('button', { name: '立即刷新' }).click()
  await expect(page.locator('.log-entry')).toHaveCount(0)
  await expect(page.getByLabel('自动刷新')).not.toBeChecked()
  await teacher.close()
})

test('筛选的真实旧响应晚到时不能覆盖新视图', async ({ page }) => {
  await login(page)
  await page.goto('/admin/logs')
  await expect(page.locator('.log-entry').first()).toBeVisible()
  await page.getByLabel('自动刷新').uncheck()
  let release: () => void = () => {}
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  let reached: () => void = () => {}
  const ready = new Promise<void>((resolve) => {
    reached = resolve
  })
  // 只延迟真实服务器响应，不伪造接口内容或状态。
  await page.route('**/api/admin/logs/runtime?**', async (route) => {
    if (new URL(route.request().url()).searchParams.get('q') === 'old-filter-no-match-zzzz') {
      const response = await route.fetch()
      reached()
      await gate
      await route.fulfill({ response })
    } else await route.continue()
  })
  await page.getByLabel('关键词', { exact: true }).fill('old-filter-no-match-zzzz')
  await page.getByRole('button', { name: '应用筛选' }).click()
  await ready
  await page.getByRole('button', { name: '重置筛选' }).click()
  await expect(page.locator('.log-entry').first()).toBeVisible()
  release()
  await expect(page.getByText('当前筛选下暂无日志')).toHaveCount(0)
  await page.unrouteAll({ behavior: 'wait' })
  await expect(page.locator('.log-entry').first()).toBeVisible()
})

test('设置响应超过刷新周期仍能读取并不会重叠请求', async ({ page }) => {
  await login(page)
  await page.goto('/admin/logs')
  let active = 0
  let maximum = 0
  await page.route('**/api/admin/logs/settings', async (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    active += 1
    maximum = Math.max(maximum, active)
    const response = await route.fetch()
    await new Promise((resolve) => setTimeout(resolve, 3500))
    await route.fulfill({ response })
    active -= 1
  })
  await page.getByRole('button', { name: '采集设置' }).click()
  await expect(page.getByRole('checkbox', { name: '写入日志文件' })).toBeVisible({
    timeout: 10_000,
  })
  expect(maximum).toBe(1)
  await page.getByRole('button', { name: '关闭采集设置' }).click()
  await page.unrouteAll({ behavior: 'wait' })
})

test('切换日志视图后不触发迟到的旧下载', async ({ page }) => {
  await login(page)
  await page.goto('/admin/logs')
  await expect(page.locator('.log-entry').first()).toBeVisible()
  let release: () => void = () => {}
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  let reached: () => void = () => {}
  const ready = new Promise<void>((resolve) => {
    reached = resolve
  })
  await page.route('**/api/admin/logs/runtime/export?**', async (route) => {
    const response = await route.fetch()
    expect(response.ok()).toBeTruthy()
    reached()
    await gate
    await route.fulfill({ response })
  })
  await page.getByRole('button', { name: '下载当前筛选' }).click()
  await ready
  await page.getByRole('tab', { name: '操作审计' }).click()
  await expect(page.getByLabel('操作者 ID')).toBeVisible()
  const downloaded = page.waitForEvent('download', { timeout: 1000 }).then(
    () => true,
    () => false,
  )
  release()
  await page.unrouteAll({ behavior: 'wait' })
  expect(await downloaded).toBe(false)
})

test('真实会话退出后日志清空并返回登录', async ({ page }) => {
  await login(page)
  await page.goto('/admin/logs')
  await expect(page.locator('.log-entry').first()).toBeVisible()
  await apiWrite(page.request, '/auth/logout', {})
  await page.getByRole('button', { name: '立即刷新' }).click()
  await expect(page).toHaveURL(/\/login\?expired=1/)
  await expect(page.locator('.log-entry')).toHaveCount(0)
})

test('桌面与390px日志页面和采集设置保持可用宽度', async ({ page }) => {
  await login(page)
  for (const [name, width, height] of [
    ['desktop', 1440, 1100],
    ['mobile', 390, 844],
  ] as const) {
    await page.setViewportSize({ width, height })
    await page.goto('/admin/logs')
    await expect(page.locator('.log-entry').first()).toBeVisible()
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true)
    await page.screenshot({
      path: `../.local/logging/frontend/${name}-runtime.png`,
      fullPage: true,
      animations: 'disabled',
    })
    await page.getByRole('tab', { name: '操作审计' }).click()
    await expect(page.getByLabel('操作者 ID')).toBeVisible()
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true)
    await page.screenshot({
      path: `../.local/logging/frontend/${name}-audit.png`,
      fullPage: true,
      animations: 'disabled',
    })
    await page.getByRole('button', { name: '采集设置' }).click()
    await expect(page.getByRole('checkbox', { name: '写入日志文件' })).toBeVisible()
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true)
    await page.screenshot({
      path: `../.local/logging/frontend/${name}-settings.png`,
      animations: 'disabled',
    })
    await page.getByRole('button', { name: '关闭采集设置' }).click()
  }
})

test('初始空审计新增多页后仍可加载更早记录', async ({ page }) => {
  test.setTimeout(60_000)
  await login(page)
  const module = `empty-history-${Date.now()}`
  await page.goto('/admin/logs')
  await page.getByRole('tab', { name: '操作审计' }).click()
  await page.getByLabel('关键词', { exact: true }).fill(module)
  await page.getByRole('button', { name: '应用筛选' }).click()
  await expect(page.getByText('当前筛选下暂无日志')).toBeVisible()
  await page.getByLabel('自动刷新').uncheck()
  for (let index = 0; index < 110; index += 1) {
    await apiWrite(page.request, `/admin/logs/debug/${module}`, { enabled: false }, 'PUT')
  }
  await page.getByRole('button', { name: '立即刷新' }).click()
  await expect(page.locator('.log-entry')).toHaveCount(100)
  await expect(page.getByRole('button', { name: '加载更早记录' })).toBeEnabled()
  await page.getByRole('button', { name: '加载更早记录' }).click()
  await expect(page.locator('.log-entry')).toHaveCount(110)
})

test('连续增量达到1000条上限后历史页紧接当前最早记录', async ({ page }) => {
  test.setTimeout(180_000)
  await login(page)
  const module = `bounded-history-${Date.now()}`
  const { csrf_token } = await (await page.request.get('/api/auth/csrf')).json()
  async function seed(count: number) {
    for (let index = 0; index < count; index += 1) {
      const response = await page.request.put(`/api/admin/logs/debug/${module}`, {
        headers: { 'X-CSRF-Token': csrf_token },
        data: { enabled: false },
      })
      expect(response.ok()).toBeTruthy()
    }
  }
  await seed(110)
  await page.goto('/admin/logs')
  await page.getByRole('tab', { name: '操作审计' }).click()
  await page.getByLabel('关键词', { exact: true }).fill(module)
  await page.getByRole('button', { name: '应用筛选' }).click()
  await expect(page.locator('.log-entry')).toHaveCount(100)
  await page.getByLabel('自动刷新').uncheck()
  await seed(1100)
  const latestPage = await (await page.request.get(`/api/admin/logs/audit?q=${module}`)).json()
  const latestId = latestPage.items[0].id as string
  await page.getByRole('button', { name: '立即刷新' }).click()
  await expect(page.locator('.log-entry')).toHaveCount(1000)
  await expect(page.getByText(/本页最多保留 1000 条/)).toBeVisible()
  // 一次最多读取十批，等3秒增量把剩余页补齐后再固定历史边界。
  await page.getByLabel('自动刷新').check()
  await expect(page.locator(`.log-entry[data-log-id="${latestId}"]`)).toBeAttached({
    timeout: 10_000,
  })
  await page.getByLabel('自动刷新').uncheck()
  const firstId = await page.locator('.log-entry').first().getAttribute('data-log-id')
  const rows: { id: string; cursor: string; formatted: string }[] = []
  let cursor: string | null = null
  do {
    const query = new URLSearchParams({ q: module })
    if (cursor) query.set('before', cursor)
    const response = await (await page.request.get(`/api/admin/logs/audit?${query}`)).json()
    rows.push(...response.items)
    cursor = response.has_more ? response.next_before : null
  } while (cursor)
  const firstIndex = rows.findIndex((row) => row.id === firstId)
  expect(firstIndex).toBeGreaterThanOrEqual(999)
  const expectedPrevious = rows[firstIndex + 1]!
  expect(expectedPrevious).toBeTruthy()
  await page.getByRole('button', { name: '加载更早记录' }).click()
  await expect(page.locator(`.log-entry[data-log-id="${expectedPrevious.id}"]`)).toBeAttached()
  await expect(page.locator('.log-entry')).toHaveCount(1000)
  const ids = await page
    .locator('.log-entry')
    .evaluateAll((elements) => elements.map((element) => (element as HTMLElement).dataset.logId))
  expect(new Set(ids).size).toBe(1000)
})
