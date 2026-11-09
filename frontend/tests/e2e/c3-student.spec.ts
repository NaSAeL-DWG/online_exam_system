import { expect, test, type Page, type TestInfo } from '@playwright/test'
import type { AttemptDetail, StudentExam } from '../../src/api/studentExams'

// 固定接口快照用于验证前端展示和交互；保存、截止交卷仍由真实业务测试覆盖。
const now = '2026-11-05T06:00:00Z'
const student = {
  id: 'c3-student',
  login_name: '2026240101',
  real_name: '界面测试学生',
  user_type: 'STUDENT',
  status: 'ACTIVATED',
  must_change_password: false,
  email: 'c3@example.com',
  phone_number: '13900000000',
  created_at: now,
}

function exam(overrides: Partial<StudentExam> = {}): StudentExam {
  return {
    id: 'c3-exam',
    title: 'C3 考试状态与作答验证',
    description: '请核对服务器保存状态。',
    audience_type: 'PUBLIC',
    status: 'RELEASED',
    start_at: '2026-11-05T05:00:00Z',
    end_at: '2026-11-05T08:00:00Z',
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
    can_start: true,
    unavailable_reason: null,
    ...overrides,
  }
}

function attempt(): AttemptDetail {
  return {
    id: 'c3-attempt',
    exam_id: 'c3-exam',
    exam_title: 'C3 考试状态与作答验证',
    attempt_no: 1,
    status: 'IN_PROGRESS',
    started_at: now,
    deadline_at: '2026-11-05T07:00:00Z',
    submitted_at: null,
    effective_submitted_at: null,
    submission_type: null,
    grading_status: 'PENDING',
    server_now: now,
    version: 1,
    token_generation: 0,
    questions: [
      {
        id: 'question-one',
        type: 'SINGLE_CHOICE',
        content: '请选择一个答案。',
        options: [
          { id: 'option-a', content: '选项甲' },
          { id: 'option-b', content: '选项乙' },
        ],
        score: '100.0',
        display_order: 1,
        answer: { id: 'answer-one', answer_data: null, version: 1, answered_at: null },
      },
    ],
  }
}

async function mockIdentity(page: Page): Promise<void> {
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: { user: student } }))
  await page.route('**/api/auth/csrf', (route) =>
    route.fulfill({ json: { csrf_token: 'c3-token' } }),
  )
}

async function captureStudent(page: Page, testInfo: TestInfo, name: string): Promise<void> {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 })
    // 等待媒体查询驱动的答题卡折叠完成，再核对小屏布局。
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(width)
    await page.screenshot({
      path: testInfo.outputPath(`${name}-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    })
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
}

test('考试详情显示服务端整场时间与三卡，结束后以灰态阻止作答', async ({ page }, testInfo) => {
  await mockIdentity(page)
  let state: Partial<StudentExam> = {}
  await page.route('**/api/student/exams/c3-exam', (route) =>
    route.fulfill({
      json: exam(state),
    }),
  )
  await page.goto('/student/exams/c3-exam')
  const summary = page.getByRole('region', { name: '考试概览' })
  await expect(summary.locator('article')).toHaveCount(3)
  await expect(summary).toContainText('距离整场考试结束还有')
  await expect(summary).toContainText('2026年11月5日')
  await expect(summary).toContainText('题量与题型进入作答后查看')
  await expect(page.getByRole('heading', { name: '详细信息' })).toBeVisible()
  await captureStudent(page, testInfo, 'exam-detail')
  state = {
    start_at: '2026-11-05T07:30:00Z',
    can_start: false,
    unavailable_reason: 'EXAM_NOT_STARTED',
  }
  await page.reload()
  await expect(summary).toContainText('距离考试开始还有')
  await expect(page.getByRole('button', { name: '暂不可开始', exact: true })).toBeDisabled()
  state = { end_at: '2026-11-05T05:59:00Z', can_start: false, unavailable_reason: 'EXAM_ENDED' }
  await page.reload()
  await expect(summary).toHaveClass(/is-unavailable/)
  await expect(summary.getByRole('timer')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '考试不可作答' })).toBeDisabled()
  await expect(page.getByRole('button', { name: '开始作答', exact: true })).toHaveCount(0)
})

test('作答标记保留深灰实心旗，保存中为旋转图标，退出先提醒且不会交卷', async ({
  page,
}, testInfo) => {
  await mockIdentity(page)
  const value = attempt()
  await page.route('**/api/student/attempts/c3-attempt', (route) => route.fulfill({ json: value }))
  await page.route('**/api/student/attempts/c3-attempt/activate', (route) =>
    route.fulfill({ json: { ...value, page_token: 'page-token' } }),
  )
  let completeSave: () => void = () => {}
  const saveGate = new Promise<void>((resolve) => {
    completeSave = resolve
  })
  let submitted = false
  await page.route('**/api/student/attempts/c3-attempt/submit', (route) => {
    submitted = true
    return route.fulfill({ json: value })
  })
  await page.route('**/api/student/attempts/c3-attempt/answers/answer-one', async (route) => {
    await saveGate
    await route.fulfill({
      json: { ...value.questions[0]!.answer, answer_data: ['option-a'], version: 2 },
    })
  })
  await page.route('**/api/student/exams/c3-exam', (route) => route.fulfill({ json: exam() }))
  await page.goto('/student/attempts/c3-attempt')
  await expect(page.locator('.attempt-identity')).toContainText('界面测试学生')
  await expect(page.locator('.attempt-identity')).toContainText('2026240101')
  await page.getByRole('button', { name: '标记待检查', exact: true }).click()
  const mark = page.getByRole('button', { name: '已标记待检查', exact: true })
  await expect(mark).toHaveAttribute('aria-pressed', 'true')
  await expect(mark).toHaveCSS('background-color', 'rgb(58, 58, 58)')
  await expect(mark.locator('svg')).toHaveCSS('fill', 'rgb(255, 255, 255)')
  await expect(page.getByRole('navigation', { name: '主导航' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '退出登录', exact: true })).toHaveCount(0)
  await captureStudent(page, testInfo, 'attempt-normal')
  await page.getByRole('radio', { name: 'A. 选项甲' }).check()
  await expect(page.locator('.save-spinner')).toBeVisible()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('保存中…')
  await captureStudent(page, testInfo, 'attempt-saving')
  completeSave()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('已保存')
  await page.getByRole('button', { name: '退出作答界面', exact: true }).click()
  await expect(page.getByText(/退出不会暂停计时/)).toBeVisible()
  await expect(page.getByText(/当前答案均已确认保存到服务器/)).toBeVisible()
  await captureStudent(page, testInfo, 'attempt-exit-modal')
  await page.getByRole('button', { name: '返回作答', exact: true }).click()
  await expect(page).toHaveURL('/student/attempts/c3-attempt')
  await page.getByRole('button', { name: '退出作答界面', exact: true }).click()
  await page.getByRole('button', { name: '我已知晓', exact: true }).click()
  await expect(page).toHaveURL('/student/exams/c3-exam')
  expect(submitted).toBe(false)
})

test('答卷首次读取失败时仍能返回我的考试', async ({ page }) => {
  await mockIdentity(page)
  await page.route('**/api/student/attempts/unavailable-attempt', (route) =>
    route.fulfill({
      status: 404,
      json: { detail: { code: 'ATTEMPT_NOT_FOUND', message: '答卷不存在' } },
    }),
  )
  await page.route('**/api/student/exams?**', (route) =>
    route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20 } }),
  )
  await page.goto('/student/attempts/unavailable-attempt')
  await expect(page.getByText('答卷不存在', { exact: false })).toBeVisible()
  await page.getByRole('link', { name: '← 返回我的考试', exact: true }).click()
  await expect(page).toHaveURL('/student/exams')
})

test('作答认证失效后允许登录重定向并移除题面，不被退出提醒阻止', async ({ page }) => {
  let expired = false
  const unauthorized = {
    status: 401,
    json: { detail: { code: 'SESSION_EXPIRED', message: '登录已过期' } },
  }
  await page.route('**/api/auth/me', (route) =>
    route.fulfill(expired ? unauthorized : { json: { user: student } }),
  )
  await page.route('**/api/auth/refresh', (route) => route.fulfill(unauthorized))
  await page.route('**/api/auth/csrf', (route) =>
    route.fulfill({ json: { csrf_token: 'c3-token' } }),
  )
  const value = attempt()
  await page.route('**/api/student/attempts/c3-attempt', (route) =>
    route.fulfill(expired ? unauthorized : { json: value }),
  )
  await page.route('**/api/student/attempts/c3-attempt/activate', (route) =>
    route.fulfill({ json: { ...value, page_token: 'page-token' } }),
  )
  await page.goto('/student/attempts/c3-attempt')
  await expect(page.getByText('请选择一个答案。', { exact: true })).toBeVisible()
  expired = true
  await page.evaluate(() => window.dispatchEvent(new Event('online')))
  await expect(page).toHaveURL(/\/login/)
  await expect(page.getByText('请选择一个答案。', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '我已知晓', exact: true })).toHaveCount(0)
})

test('退出时保存失败明确提示本地修改未同步，浏览器返回同样需要确认', async ({ page }) => {
  await mockIdentity(page)
  const value = attempt()
  await page.route('**/api/student/attempts/c3-attempt', (route) => route.fulfill({ json: value }))
  await page.route('**/api/student/attempts/c3-attempt/activate', (route) =>
    route.fulfill({ json: { ...value, page_token: 'page-token' } }),
  )
  await page.route('**/api/student/attempts/c3-attempt/answers/answer-one', (route) =>
    route.fulfill({
      status: 503,
      json: { detail: { code: 'SAVE_UNAVAILABLE', message: '保存暂不可用' } },
    }),
  )
  await page.route('**/api/student/exams/c3-exam', (route) => route.fulfill({ json: exam() }))
  await page.route('**/api/student/exams/c3-exam/attempts', (route) =>
    route.fulfill({ json: value }),
  )
  await page.goto('/student/exams/c3-exam')
  await page.getByRole('button', { name: '开始作答', exact: true }).click()
  await page.getByRole('radio', { name: 'A. 选项甲' }).check()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('保存失败')
  await page.evaluate(() => history.back())
  await expect(page.getByText(/仍有 1 题修改未确认保存到服务器/)).toBeVisible()
  await expect(page.getByText(/尚未同步的本地输入不计入自动提交/)).toBeVisible()
  await page.getByRole('button', { name: '返回作答', exact: true }).click()
  await expect(page).toHaveURL('/student/attempts/c3-attempt')
})

test('掌握情况可与题型搜索共同筛选，并能清除条件', async ({ page }) => {
  await mockIdentity(page)
  const requests: URL[] = []
  await page.route('**/api/student/mistakes?**', (route) => {
    requests.push(new URL(route.request().url()))
    return route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20 } })
  })
  await page.goto('/student/mistakes')
  await page.getByLabel('搜索错题').fill('积分')
  await page.getByRole('combobox', { name: '题型筛选' }).click()
  await page.getByRole('option', { name: '单选题', exact: true }).click()
  await page.getByRole('combobox', { name: '掌握状态' }).click()
  await page.getByRole('option', { name: '待复习', exact: true }).click()
  await page.getByRole('button', { name: '筛选错题', exact: true }).click()
  await expect.poll(() => requests.at(-1)?.searchParams.get('mastered')).toBe('false')
  expect(requests.at(-1)?.searchParams.get('q')).toBe('积分')
  expect(requests.at(-1)?.searchParams.get('type')).toBe('SINGLE_CHOICE')
  await page.getByRole('button', { name: '清除筛选', exact: true }).click()
  await expect.poll(() => requests.at(-1)?.searchParams.get('mastered')).toBeNull()
  await expect(page.getByLabel('搜索错题')).toHaveValue('')
})

test('未公布与待批改的提示按内容适应高度', async ({ page }, testInfo) => {
  await mockIdentity(page)
  let published = false
  await page.route('**/api/student/results/c3-exam', (route) =>
    route.fulfill({
      json: {
        exam_id: 'c3-exam',
        title: 'C3 结果高度验证',
        exam_status: 'RELEASED',
        result_state: published ? 'PUBLISHED' : 'NOT_PUBLISHED',
        participant_status: 'ACTIVE',
        end_at: now,
        total_score: '100.0',
        allow_review: true,
        can_review: false,
        attempts_count: 1,
        final_attempt_id: 'c3-attempt',
        final_attempt_no: 1,
        grading_status: 'GRADING',
        final_score: null,
        submitted_at: now,
        attempts: [
          {
            id: 'c3-attempt',
            attempt_no: 1,
            status: 'SUBMITTED',
            started_at: now,
            submitted_at: now,
            grading_status: 'GRADING',
            final_score: null,
            can_review: false,
          },
        ],
      },
    }),
  )
  await page.goto('/student/results/c3-exam')
  const notice = page.locator('.result-visibility')
  await expect(notice).toContainText('结果未公布')
  expect((await notice.boundingBox())!.height).toBeLessThan(180)
  published = true
  await page.getByRole('button', { name: '刷新结果', exact: true }).click()
  await expect(page.getByText('最后一次作答正在批改', { exact: true })).toBeVisible()
  const pending = page.getByRole('region', { name: '最终成绩' }).locator('.n-alert')
  expect((await pending.boundingBox())!.height).toBeLessThan(180)
  await captureStudent(page, testInfo, 'result-pending')
})
