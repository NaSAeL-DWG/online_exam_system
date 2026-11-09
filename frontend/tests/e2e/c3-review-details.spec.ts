import { expect, test, type Locator, type Page, type TestInfo } from '@playwright/test'
import type { StudentExam } from '../../src/api/studentExams'

// 全部接口使用固定快照，视觉复核与密码规则检查不读写真实账号数据。
const now = '2026-11-06T06:00:00Z'
const student = {
  id: 'c3-review-student',
  login_name: '2026240101',
  real_name: '界面复核学生',
  user_type: 'STUDENT',
  status: 'ACTIVATED',
  must_change_password: false,
  email: 'c3-review@example.com',
  phone_number: '13900000000',
  created_at: now,
}

function exam(ended: boolean): StudentExam {
  return {
    id: 'c3-review-exam',
    title: '高等数学阶段测验',
    description: '请在规定时间内完成作答，交卷前核对答案保存状态。',
    audience_type: 'PUBLIC',
    status: 'RELEASED',
    start_at: '2026-11-06T05:00:00Z',
    end_at: ended ? '2026-11-06T05:59:00Z' : '2026-11-06T08:00:00Z',
    duration_seconds: 3600,
    max_attempts: 2,
    total_score: '100.0',
    server_now: now,
    participant_status: 'ASSIGNED',
    cancelled_reason: null,
    used_attempts: 0,
    remaining_attempts: 2,
    current_attempt_id: null,
    current_attempt_status: null,
    can_start: !ended,
    unavailable_reason: ended ? 'EXAM_ENDED' : null,
  }
}

async function mockApi(
  page: Page,
  options: { publicPage?: boolean; exam?: () => StudentExam } = {},
) {
  const unexpected: string[] = []
  const writes: Array<{ path: string; body: Record<string, string> }> = []
  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    // 开发服务器的 /src/api/*.ts 是源码模块，不属于后端接口。
    if (!path.startsWith('/api/')) {
      await route.fallback()
      return
    }
    if (path === '/api/auth/me') {
      await route.fulfill({ json: { user: options.publicPage ? null : student } })
    } else if (path === '/api/auth/csrf') {
      await route.fulfill({ json: { csrf_token: 'c3-review-token' } })
    } else if (path === '/api/student/exams/c3-review-exam' && options.exam) {
      await route.fulfill({ json: options.exam() })
    } else if (path === '/api/auth/password' || path === '/api/auth/register') {
      writes.push({ path, body: request.postDataJSON() })
      await route.fulfill({ json: { application: { id: 'c3-review-application' } } })
    } else {
      unexpected.push(`${request.method()} ${path}`)
      await route.fulfill({ status: 404, json: { detail: '未配置的界面测试接口' } })
    }
  })
  return { unexpected, writes }
}

async function capture(page: Page, testInfo: TestInfo, name: string, width: number) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(width)
  await page.screenshot({
    path: testInfo.outputPath(`${name}-${width}.png`),
    fullPage: true,
    animations: 'disabled',
  })
}

async function expectRequirementsOrder(page: Page, confirmation: Locator, submit: Locator) {
  const requirements = page.getByRole('region', { name: '密码要求', exact: true })
  await expect(requirements).toHaveCount(1)
  await expect(requirements).toContainText('请输入 10—256 个字符。')
  await expect(requirements).toContainText('密码强度提示仅供参考，不限制字符种类或组合。')
  await expect(page.getByText('仅作参考，密码需10—256个字符', { exact: true })).toHaveCount(0)
  const fieldBottom = await confirmation.evaluate(
    (input) => input.closest('.n-form-item')!.getBoundingClientRect().bottom,
  )
  const ruleBox = await requirements.boundingBox()
  const buttonBox = await submit.boundingBox()
  expect(ruleBox).not.toBeNull()
  expect(buttonBox).not.toBeNull()
  expect(ruleBox!.y).toBeGreaterThanOrEqual(fieldBottom)
  expect(buttonBox!.y).toBeGreaterThanOrEqual(ruleBox!.y + ruleBox!.height)
  // 密码要求独立于字段容器，提交前即可整体阅读。
  expect(
    await requirements.locator('xpath=ancestor::*[contains(@class,"n-form-item")]').count(),
  ).toBe(0)
}

test('考试详情的三张信息卡在开放与结束状态均保留统一细边框', async ({ page }, testInfo) => {
  let ended = false
  const api = await mockApi(page, { exam: () => exam(ended) })
  await page.goto('/student/exams/c3-review-exam')
  const summary = page.getByRole('region', { name: '考试概览' })
  const cards = summary.locator('article')
  for (const state of ['open', 'ended']) {
    if (state === 'ended') {
      ended = true
      await page.reload()
      await expect(summary).toHaveClass(/is-unavailable/)
      await expect(page.getByRole('button', { name: '考试不可作答' })).toBeDisabled()
    }
    await expect(cards).toHaveCount(3)
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 960 })
      for (const card of await cards.all()) {
        const borders = await card.evaluate((element) => {
          const style = getComputedStyle(element)
          return {
            topWidth: style.borderTopWidth,
            sideWidth: style.borderLeftWidth,
            topColor: style.borderTopColor,
            sideColor: style.borderLeftColor,
            background: style.backgroundColor,
          }
        })
        expect(borders.topWidth).toBe('1px')
        expect(borders.topWidth).toBe(borders.sideWidth)
        expect(borders.topColor).toBe(borders.sideColor)
        expect(borders.background).toBe(ended ? 'rgb(244, 244, 244)' : 'rgb(255, 255, 255)')
      }
      await capture(page, testInfo, `exam-detail-${state}`, width)
    }
  }
  expect(api.unexpected).toEqual([])
  expect(api.writes).toEqual([])
})

test('修改密码在表单与保存按钮之间单列密码要求且保持原有长度规则', async ({ page }, testInfo) => {
  const api = await mockApi(page)
  await page.goto('/account/password')
  const current = page.getByLabel('当前密码', { exact: true })
  const password = page.getByLabel('新密码', { exact: true })
  const confirmation = page.getByLabel('确认新密码', { exact: true })
  const submit = page.getByRole('button', { name: '保存新密码', exact: true })
  await current.fill('current-password')
  await password.fill('abcdefghij')
  await confirmation.fill('abcdefghij')
  await expect(page.getByText('密码强度：弱', { exact: true })).toBeVisible()
  await expect(page.getByText('密码已匹配', { exact: true })).toBeVisible()
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 960 })
    await expectRequirementsOrder(page, confirmation, submit)
    await capture(page, testInfo, 'password-requirements', width)
  }
  await password.fill('abcdefghi')
  await confirmation.fill('abcdefghi')
  await submit.click()
  await expect(page.locator('#password-new_password-error')).toHaveText('至少需要10个字符')
  expect(api.writes).toHaveLength(0)
  await password.fill('a'.repeat(257))
  await confirmation.fill('a'.repeat(257))
  await submit.click()
  await expect(page.locator('#password-new_password-error')).toHaveText('最多允许256个字符')
  expect(api.writes).toHaveLength(0)
  await password.fill('abcdefghij')
  await confirmation.fill('abcdefghij')
  await submit.click()
  await expect(page).toHaveURL('/login')
  expect(api.writes).toEqual([
    {
      path: '/api/auth/password',
      body: { current_password: 'current-password', new_password: 'abcdefghij' },
    },
  ])
  expect(api.unexpected).toEqual([])
})

test('注册在输入表单后单列密码要求且允许符合长度要求的弱密码', async ({ page }, testInfo) => {
  const api = await mockApi(page, { publicPage: true })
  await page.goto('/register')
  await page.getByLabel('姓名', { exact: true }).fill('界面复核学生')
  await page.getByLabel('学号', { exact: true }).fill('2026240101')
  await page.getByLabel('邮箱', { exact: true }).fill('c3-review@example.com')
  await page.getByLabel('手机号', { exact: true }).fill('13900000000')
  const password = page.getByLabel('密码', { exact: true })
  const confirmation = page.getByLabel('确认密码', { exact: true })
  const submit = page.getByRole('button', { name: '提交注册', exact: true })
  await password.fill('abcdefghij')
  await confirmation.fill('abcdefghij')
  await expect(page.getByText('密码强度：弱', { exact: true })).toBeVisible()
  await expect(page.getByText('密码已匹配', { exact: true })).toBeVisible()
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 960 })
    await expectRequirementsOrder(page, confirmation, submit)
    await capture(page, testInfo, 'register-requirements', width)
  }
  await password.fill('abcdefghi')
  await confirmation.fill('abcdefghi')
  await submit.click()
  await expect(page.locator('#register-password-error')).toHaveText('至少需要10个字符')
  expect(api.writes).toHaveLength(0)
  await password.fill('abcdefghij')
  await confirmation.fill('abcdefghij')
  await submit.click()
  await expect(page.getByRole('heading', { name: '申请已提交' })).toBeVisible()
  expect(api.writes).toHaveLength(1)
  expect(api.writes[0]!.body.password).toBe('abcdefghij')
  expect(api.unexpected).toEqual([])
})
