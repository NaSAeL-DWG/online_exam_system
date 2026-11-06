import { expect, test, type Page } from '@playwright/test'
import type { StudentExam } from '../../src/api/studentExams'
import type { UserRole } from '../../src/types'

async function identity(page: Page, role: UserRole): Promise<void> {
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({
      json: {
        user: {
          id: 'c3-home-user',
          login_name: 'c3-home',
          real_name: '界面测试用户',
          user_type: role,
          status: 'ACTIVATED',
          must_change_password: false,
          email: 'home@example.com',
          phone_number: '13900000000',
          created_at: '2026-11-05T00:00:00Z',
        },
      },
    }),
  )
}

function studentExam(overrides: Partial<StudentExam>): StudentExam {
  return {
    id: 'available',
    title: '可参加的考试',
    description: null,
    audience_type: 'PUBLIC',
    status: 'RELEASED',
    start_at: '2026-11-05T00:00:00Z',
    end_at: '2026-11-05T09:00:00Z',
    duration_seconds: 3600,
    max_attempts: 2,
    total_score: '100',
    server_now: '2026-11-05T06:00:00Z',
    participant_status: 'ASSIGNED',
    cancelled_reason: null,
    used_attempts: 0,
    remaining_attempts: 2,
    current_attempt_id: null,
    current_attempt_status: null,
    can_start: true,
    unavailable_reason: null,
    ...overrides,
  }
}

test('学生首页优先继续作答，近期记录不冒充全局考试统计', async ({ page }) => {
  await identity(page, 'STUDENT')
  const items = [
    studentExam({
      id: 'ended',
      title: '已经结束的考试',
      can_start: false,
      end_at: '2026-11-05T01:00:00Z',
    }),
    studentExam({}),
    studentExam({
      id: 'active',
      title: '正在作答的考试',
      current_attempt_id: 'active-attempt',
      current_attempt_status: 'IN_PROGRESS',
    }),
  ]
  await page.route('**/api/student/exams?**', (route) =>
    route.fulfill({ json: { items, total: 31, page: 1, page_size: 20 } }),
  )
  await page.route('**/api/student/attempts/active-attempt', (route) =>
    route.fulfill({
      json: {
        id: 'active-attempt',
        exam_id: 'active',
        attempt_no: 1,
        status: 'IN_PROGRESS',
        server_now: '2026-11-05T06:00:00Z',
        deadline_at: '2026-11-05T07:00:00Z',
        questions: [],
      },
    }),
  )
  await page.route('**/api/student/results?**', (route) =>
    route.fulfill({ json: { items: [], total: 0 } }),
  )
  await page.route('**/api/student/mistakes?**', (route) =>
    route.fulfill({ json: { items: [], total: 0 } }),
  )
  await page.goto('/home')
  await expect(page.getByRole('region', { name: '当前考试', exact: true })).toContainText(
    '正在作答的考试',
  )
  await expect(
    page
      .getByRole('region', { name: '当前考试', exact: true })
      .getByRole('button', { name: '继续作答' }),
  ).toBeVisible()
  await expect(page.locator('.student-next-exam h3')).toHaveText(['可参加的考试'])
  await expect(page.getByRole('region', { name: '学习记录', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '我的账号', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '全部考试 ↗' })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
})

test('教师首页按真实待办总数显示并优先继续阅卷', async ({ page }) => {
  await identity(page, 'TEACHER')
  await page.route('**/api/staff/exams?**', (route) =>
    route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 4 } }),
  )
  await page.route('**/api/staff/grading-tasks?**', (route) => {
    const query = new URL(route.request().url()).searchParams
    expect(query.get('assigned_teacher_id')).toBe('c3-home-user')
    const active = query.get('status') === 'IN_PROGRESS'
    return route.fulfill({
      json: {
        items: [
          {
            id: active ? 'active' : 'pending',
            attempt_id: active ? 'attempt-1' : 'attempt-2',
            exam_id: 'home-exam',
            exam_title: active ? '继续批阅的答卷' : '等待批阅的答卷',
            student: { real_name: '测试学生', login_name: '20260001' },
            attempt_no: 1,
            status: active ? 'IN_PROGRESS' : 'PENDING',
            can_grade: true,
          },
        ],
        total: active ? 2 : 7,
        page: 1,
        page_size: 4,
      },
    })
  })
  await page.goto('/home')
  await expect(page.getByText('待阅与阅卷中共 9 份，优先继续已开始的答卷。')).toBeVisible()
  await expect(page.locator('.home-record h3')).toHaveText(['继续批阅的答卷', '等待批阅的答卷'])
  await expect(page.getByRole('link', { name: '进入阅卷', exact: true }).first()).toHaveAttribute(
    'href',
    '/staff/attempts/attempt-1',
  )
})

test('管理员保留考试管理并将旧阅卷链接导回考试管理', async ({ page }) => {
  await identity(page, 'ADMIN')
  await page.route('**/api/staff/exams?**', (route) =>
    route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20 } }),
  )
  await page.goto('/home')
  await expect(
    page
      .getByRole('navigation', { name: '主导航' })
      .getByRole('link', { name: '考试管理', exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('link', { name: /阅卷工作台/ })).toHaveCount(0)
  for (const legacyPath of ['/staff/grading-tasks', '/staff/attempts/legacy-attempt']) {
    await page.goto(legacyPath)
    await expect(page).toHaveURL('/staff/exams')
    await expect(page.getByRole('heading', { name: '考试管理', exact: true })).toBeVisible()
  }
})
