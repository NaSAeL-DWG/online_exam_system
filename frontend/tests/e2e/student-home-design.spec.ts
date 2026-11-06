import { expect, test, type Page } from '@playwright/test'

const now = '2026-11-03T06:47:42Z'
const examBase = {
  description: null,
  audience_type: 'PUBLIC',
  status: 'RELEASED',
  start_at: '2026-11-03T06:00:00Z',
  end_at: '2026-11-03T08:00:00Z',
  duration_seconds: 5400,
  max_attempts: 2,
  total_score: '100',
  server_now: now,
  participant_status: 'ASSIGNED',
  cancelled_reason: null,
  used_attempts: 0,
  remaining_attempts: 2,
  current_attempt_id: null,
  current_attempt_status: null,
  can_start: false,
  unavailable_reason: null,
}
async function fixture(page: Page) {
  await page.clock.install({ time: new Date(now) })
  await page.clock.pauseAt(new Date('2026-11-03T06:47:43Z'))
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({
      json: {
        user: {
          id: 'home-student',
          login_name: '20260101',
          real_name: '林同学',
          user_type: 'STUDENT',
          status: 'ACTIVATED',
          must_change_password: false,
        },
      },
    }),
  )
  await page.route('**/api/student/exams?**', (route) =>
    route.fulfill({
      json: {
        items: [
          {
            ...examBase,
            id: 'current',
            title: '高等数学 · 期中测验',
            current_attempt_id: 'current-attempt',
            current_attempt_status: 'IN_PROGRESS',
            used_attempts: 1,
            remaining_attempts: 1,
          },
          {
            ...examBase,
            id: 'later',
            title: '高等数学 · 积分专项练习',
            start_at: '2026-11-05T06:00:00Z',
            end_at: '2026-11-05T08:00:00Z',
            duration_seconds: 3600,
          },
          {
            ...examBase,
            id: 'available',
            title: '线性代数 · 第二章单元测验',
            can_start: true,
            start_at: '2026-11-03T00:00:00Z',
            end_at: '2026-11-03T12:00:00Z',
            duration_seconds: 2700,
          },
        ],
        total: 3,
        page: 1,
        page_size: 20,
      },
    }),
  )
  await page.route('**/api/student/attempts/current-attempt', (route) =>
    route.fulfill({
      json: {
        id: 'current-attempt',
        exam_id: 'current',
        attempt_no: 1,
        status: 'IN_PROGRESS',
        deadline_at: '2026-11-03T07:30:00Z',
        server_now: now,
        questions: Array.from({ length: 20 }, (_, i) => ({
          answer: { answer_data: i < 8 ? false : null },
        })),
      },
    }),
  )
  let published = true
  await page.route('**/api/student/results?**', (route) =>
    route.fulfill({
      json: {
        items: [
          {
            exam_id: 'result',
            title: '线性代数 · 第一章测验',
            result_state: published ? 'PUBLISHED' : 'CORRECTING',
            final_score: published ? '86' : null,
            total_score: '100',
            submitted_at: '2026-10-28T06:00:00Z',
          },
        ],
        total: 1,
      },
    }),
  )
  await page.route('**/api/student/mistakes?**', (route) => {
    expect(new URL(route.request().url()).searchParams.get('mastered')).toBe('false')
    return route.fulfill({
      json: {
        items: published ? [{ knowledge_tags: ['连续与可导', '中值定理'] }] : [],
        total: published ? 12 : 0,
      },
    })
  })
  return {
    withdraw: () => {
      published = false
    },
  }
}

test('学生工作台还原C3层次，个人倒计时与已保存进度来自只读接口', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  const control = await fixture(page)
  const writes: string[] = []
  page.on('request', (request) => {
    if (request.method() !== 'GET') writes.push(request.url())
  })
  await page.goto('/home')
  await expect(page.getByRole('heading', { name: '下午好，林同学' })).toBeVisible()
  await expect(page.getByRole('timer')).toHaveText('42:18')
  await expect(page.getByText('继续上次作答，服务器已保存 8 / 20 题的答案。')).toBeVisible()
  await expect(page.locator('.student-next-exam h3')).toHaveText([
    '线性代数 · 第二章单元测验',
    '高等数学 · 积分专项练习',
  ])
  await expect(page.getByRole('region', { name: '学习记录' })).toContainText('86 / 100')
  await expect(page.getByRole('button', { name: '12 题 →' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '我的账号' })).toHaveCount(0)
  expect(writes).toEqual([])
  await page.screenshot({
    path: testInfo.outputPath('student-home-1440.png'),
    fullPage: true,
    animations: 'disabled',
  })
  await page.clock.runFor(1000)
  await expect(page.getByRole('timer')).toHaveText('42:17')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({
    path: testInfo.outputPath('student-home-390.png'),
    fullPage: true,
    animations: 'disabled',
  })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390)
  control.withdraw()
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await expect(page.locator('.student-learning-score')).toHaveCount(0)
  await expect(page.getByRole('region', { name: '学习记录' })).toContainText('结果更正中')
  await expect(page.getByRole('button', { name: '0 题 →' })).toBeVisible()
})

test('作答进度读取失败时不编造倒计时或已保存信息', async ({ page }) => {
  await fixture(page)
  await page.route('**/api/student/attempts/current-attempt', (route) =>
    route.fulfill({ status: 503, json: {} }),
  )
  await page.goto('/home')
  await expect(page.getByText('作答进度暂时无法读取。')).toBeVisible()
  await expect(page.getByRole('timer')).toHaveCount(0)
  await expect(
    page
      .getByRole('region', { name: '当前考试' })
      .getByRole('button', { name: '查看考试', exact: true }),
  ).toBeVisible()
})
