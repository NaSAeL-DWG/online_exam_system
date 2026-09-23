import { expect, test, type Page } from '@playwright/test'

async function login(page: Page, loginName: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(loginName)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
}

async function createTeacherAndLogin(page: Page): Promise<string> {
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  await expect(page.getByRole('heading', { name: '管理工作台' })).toBeVisible()
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const teacherNo = `F${suffix}`
  const csrf = await page.request.get('/api/auth/csrf')
  const { csrf_token: csrfToken } = await csrf.json()
  const response = await page.request.post('/api/admin/teachers', {
    headers: { 'X-CSRF-Token': csrfToken },
    data: {
      teacher_no: teacherNo,
      real_name: '认证故障测试教师',
      email: `fault-${suffix}@example.com`,
      phone_number: '13800000000',
      temporary_password: 'Teacher123!',
    },
  })
  expect(response.ok()).toBeTruthy()
  await page.getByRole('button', { name: '退出登录' }).click()
  await login(page, teacherNo, 'Teacher123!')
  await expect(page.getByRole('heading', { name: '请先修改临时密码' })).toBeVisible()
  return teacherNo
}

test.beforeEach(() => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
})

test('改密响应丢失后不重复提交，用户可以用新密码重新登录', async ({ page }) => {
  const teacherNo = await createTeacherAndLogin(page)
  let passwordRequests = 0
  await page.route('**/api/auth/password', async (route) => {
    passwordRequests += 1
    const response = await route.fetch()
    expect(response.status()).toBe(204)
    await route.abort('connectionreset')
  })
  await page.getByLabel('当前密码').fill('Teacher123!')
  await page.getByLabel('新密码', { exact: true }).fill('Teacher456!')
  await page.getByLabel('确认新密码').fill('Teacher456!')
  await page.getByRole('button', { name: '保存新密码' }).click()
  await expect(
    page.getByText('密码修改结果尚未确认，请使用新密码尝试登录；不要直接重复提交。'),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: '保存新密码' })).toBeDisabled()
  expect(passwordRequests).toBe(1)
  await page.screenshot({
    path: 'test-results/visual/password-result-unknown.png',
    fullPage: true,
    animations: 'disabled',
  })
  await page.getByRole('button', { name: '重新登录确认' }).click()
  await page.getByLabel('登录账号').fill(teacherNo)
  await page.getByLabel('密码').fill('Teacher456!')
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '教师工作台' })).toBeVisible()
})

test('改密已成功且旧登录状态待清理时，仍提示使用新密码登录', async ({ page }) => {
  const teacherNo = await createTeacherAndLogin(page)
  await page.route('**/api/auth/password', async (route) => {
    const response = await route.fetch()
    expect(response.status()).toBe(204)
    await route.fulfill({
      response,
      headers: { ...response.headers(), 'X-Session-Cleanup': 'pending' },
    })
  })
  await page.getByLabel('当前密码').fill('Teacher123!')
  await page.getByLabel('新密码', { exact: true }).fill('Teacher456!')
  await page.getByLabel('确认新密码').fill('Teacher456!')
  await page.getByRole('button', { name: '保存新密码' }).click()
  await expect(
    page.getByText('密码修改成功，旧登录状态正在清理，请使用新密码重新登录'),
  ).toBeVisible()
  await page.screenshot({
    path: 'test-results/visual/password-cleanup-pending.png',
    fullPage: true,
    animations: 'disabled',
  })
  await login(page, teacherNo, 'Teacher456!')
  await expect(page.getByRole('heading', { name: '教师工作台' })).toBeVisible()
})

test('联系方式已保存但响应内容损坏时，先读取最新资料再允许保存', async ({ page }) => {
  const teacherNo = await createTeacherAndLogin(page)
  await page.getByLabel('当前密码').fill('Teacher123!')
  await page.getByLabel('新密码', { exact: true }).fill('Teacher456!')
  await page.getByLabel('确认新密码').fill('Teacher456!')
  await page.getByRole('button', { name: '保存新密码' }).click()
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
  await login(page, teacherNo, 'Teacher456!')
  await expect(page.getByRole('heading', { name: '教师工作台' })).toBeVisible()
  await page.goto('/account/contacts')
  let writes = 0
  await page.route('**/api/auth/contacts', async (route) => {
    writes += 1
    const response = await route.fetch()
    expect(response.ok()).toBeTruthy()
    await route.fulfill({ response, body: '{"user":', contentType: 'application/json' })
  })
  const email = `updated-${Date.now()}@example.com`
  await page.getByLabel('邮箱').fill(email)
  await page.getByLabel('当前密码').fill('Teacher456!')
  await page.getByRole('button', { name: '保存联系方式' }).click()
  await expect(
    page.getByText('操作结果尚未确认，请先查看最新状态，不要直接重复提交。'),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: '保存联系方式' })).toBeDisabled()
  await page.getByRole('button', { name: '重新读取资料' }).click()
  await expect(page.getByLabel('邮箱')).toHaveValue(email)
  await expect(page.getByRole('button', { name: '保存联系方式' })).toBeEnabled()
  expect(writes).toBe(1)
})

test('刷新凭据交付中断时要求重新登录，不把它提示成普通网络重试', async ({ page, context }) => {
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  await expect(page.getByRole('heading', { name: '管理工作台' })).toBeVisible()
  await context.clearCookies({ name: 'access_token' })
  let refreshRequests = 0
  await page.route('**/api/auth/refresh', async (route) => {
    refreshRequests += 1
    const response = await route.fetch()
    expect(response.ok()).toBeTruthy()
    await route.abort('connectionreset')
  })
  await page.getByText('账号管理', { exact: true }).click()
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
  await expect(page.getByText('登录状态更新未能确认，请重新登录。')).toBeVisible()
  expect(refreshRequests).toBe(1)
})

test('刷新前服务暂不可用保留当前页面，恢复后可以手动重试', async ({ page, context }) => {
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  await expect(page.getByRole('heading', { name: '管理工作台' })).toBeVisible()
  await context.clearCookies({ name: 'access_token' })
  await page.route('**/api/auth/refresh', (route) =>
    route.fulfill({
      status: 503,
      json: {
        detail: { code: 'AUTH_SERVICE_UNAVAILABLE', message: '认证服务暂时不可用，请稍后重试' },
      },
    }),
  )
  await page.getByText('账号管理', { exact: true }).click()
  await expect(page.getByText('认证服务暂时不可用，请稍后重试')).toBeVisible()
  await expect(page.getByRole('heading', { name: '账号管理' })).toBeVisible()
  await page.unroute('**/api/auth/refresh')
  await page.getByRole('button', { name: '重试加载' }).click()
  await expect(page.getByText('认证服务暂时不可用，请稍后重试')).toBeHidden()
  await expect(page.getByRole('row').nth(1)).toBeVisible()
})

test('退出遇到服务故障时说明未完成并保留当前身份，恢复后可重试退出', async ({ page }) => {
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  await expect(page.getByRole('heading', { name: '管理工作台' })).toBeVisible()
  await page.route('**/api/auth/logout', (route) =>
    route.fulfill({
      status: 503,
      json: {
        detail: { code: 'AUTH_SERVICE_UNAVAILABLE', message: '认证服务暂时不可用，请稍后重试' },
      },
    }),
  )
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page.getByText('认证服务暂时不可用，请稍后重试')).toBeVisible()
  await expect(page.getByRole('heading', { name: '管理工作台' })).toBeVisible()
  await page.unroute('**/api/auth/logout')
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
})
