import { expect, test, type Page, type TestInfo } from '@playwright/test'
import type { StudentApplication, User } from '../../src/types'

// 用固定接口快照核对公共页布局与提交契约，不改动真实账号。
const user: User = {
  id: 'public-design-student',
  login_name: '2026240101',
  real_name: '林予安',
  email: 'lin@example.com',
  phone_number: '13800000001',
  user_type: 'STUDENT',
  status: 'ACTIVATED',
  must_change_password: false,
  created_at: '2026-11-06T02:26:00Z',
}

async function identity(page: Page, value: User | null) {
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: { user: value } }))
  await page.route('**/api/auth/csrf', (route) =>
    route.fulfill({ json: { csrf_token: 'public-design-token' } }),
  )
}

async function capture(page: Page, info: TestInfo, name: string) {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 960 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(width)
    await page.screenshot({
      path: info.outputPath(`${name}-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    })
  }
}

test('登录保留凭据错误反馈，注册限宽且返回入口紧邻表单', async ({ page }, info) => {
  await identity(page, null)
  let payload: unknown
  await page.route('**/api/auth/login', async (route) => {
    payload = route.request().postDataJSON()
    await route.fulfill({
      status: 401,
      json: { detail: { code: 'INVALID_CREDENTIALS', message: '账号或密码不正确' } },
    })
  })
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: '账号登录' })).toBeVisible()
  await page.getByLabel('登录账号').fill('2026240101')
  await page.getByLabel('密码', { exact: true }).fill('incorrect-password')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('账号或密码不正确')
  expect(payload).toEqual({ login_name: '2026240101', password: 'incorrect-password' })
  await capture(page, info, 'login')
  await page.getByRole('link', { name: '学生注册', exact: true }).click()
  await expect(page.getByRole('link', { name: '← 返回登录' })).toBeVisible()
  await capture(page, info, 'register')
  await page.setViewportSize({ width: 1440, height: 960 })
  const box = await page.locator('.auth-workspace--register').boundingBox()
  expect(box!.width).toBe(760)
  expect(box!.x).toBe((1440 - 760) / 2)
})

test('联系方式单栏保存仍验证当前密码并清空凭据', async ({ page }, info) => {
  await identity(page, user)
  const writes: unknown[] = []
  await page.route('**/api/auth/contacts', async (route) => {
    const body = route.request().postDataJSON()
    writes.push(body)
    await route.fulfill({ json: { user: { ...user, email: body.email } } })
  })
  await page.goto('/account/contacts')
  await expect(page.getByLabel('邮箱', { exact: true })).toHaveValue(user.email)
  await capture(page, info, 'contacts')
  await page.getByLabel('邮箱', { exact: true }).fill('updated@example.com')
  await page.getByRole('button', { name: '保存联系方式' }).click()
  expect(writes).toHaveLength(0)
  await expect(page.getByLabel('当前密码')).toHaveAttribute('aria-invalid', 'true')
  await page.getByLabel('当前密码').fill('current-password')
  await page.getByRole('button', { name: '保存联系方式' }).click()
  await expect(page.getByLabel('当前密码')).toHaveValue('')
  expect(writes).toEqual([
    {
      email: 'updated@example.com',
      phone_number: user.phone_number,
      current_password: 'current-password',
    },
  ])
  await page.goto('/account/password')
  await expect(page.getByRole('heading', { name: '修改密码', exact: true })).toBeVisible()
  await capture(page, info, 'password')
})

test('申请进度保留拒绝原因和资料更正，重新提交后展示待审核', async ({ page }, info) => {
  await identity(page, { ...user, status: 'WAITING_ACTIVATE' })
  let application: StudentApplication = {
    id: 'public-design-application',
    status: 'REJECTED',
    reason: '请核对学号与名册是否一致。',
    submitted_profile: {
      student_no: user.login_name,
      real_name: user.real_name,
      email: user.email,
      phone_number: user.phone_number,
    },
    submitted_at: '2026-11-06T02:26:00Z',
    reviewed_at: '2026-11-06T03:00:00Z',
    reviewer_id: 'teacher',
  }
  const writes: unknown[] = []
  await page.route('**/api/student/application', async (route) => {
    if (route.request().method() === 'PUT') {
      const profile = route.request().postDataJSON()
      writes.push(profile)
      application = { ...application, status: 'PENDING', reason: null, submitted_profile: profile }
    }
    await route.fulfill({ json: { application } })
  })
  await page.goto('/student/application')
  await expect(page.getByRole('heading', { name: '申请未通过' })).toBeVisible()
  await expect(page.getByRole('alert')).toContainText(application.reason!)
  await capture(page, info, 'application-rejected')
  await page.getByLabel('学号', { exact: true }).fill('2026240102')
  await page.getByRole('button', { name: '重新提交审核' }).click()
  await expect(page.getByRole('heading', { name: '申请审核中' })).toBeVisible()
  await expect(page.getByRole('link', { name: '维护联系方式' })).toBeVisible()
  expect(writes).toEqual([{ ...application.submitted_profile, student_no: '2026240102' }])
  await capture(page, info, 'application-pending')
})
