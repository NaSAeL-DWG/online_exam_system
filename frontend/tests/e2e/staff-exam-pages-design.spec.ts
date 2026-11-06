import { expect, test, type Page, type TestInfo } from '@playwright/test'
import type { Exam } from '../../src/api/exams'
import type { StaffAttemptDetail, GradingTaskSummary } from '../../src/api/grading'

// 固定接口快照仅用于页面、交互和权限回归，不触碰真实考试与评分数据。
const teacher = {
  id: 'teacher-c3',
  login_name: 'T2026008',
  real_name: '陈老师',
  user_type: 'TEACHER',
  status: 'ACTIVATED',
  must_change_password: false,
  email: 'c3@example.com',
  phone_number: '13900000000',
  created_at: '2026-11-06T00:00:00Z',
}
const student = {
  id: 'student-c3',
  login_name: '2026240101',
  real_name: '林予安',
  user_type: 'STUDENT',
  status: 'ACTIVATED',
} as const
const baseExam: Exam = {
  id: 'exam-c3',
  title: '高等数学 · 积分专项练习',
  description: '请认真检查作答过程，按时提交答卷。',
  creator_id: teacher.id,
  source_paper_id: 'paper-c3',
  status: 'DRAFT',
  version: 1,
  audience_type: 'RESTRICTED',
  start_at: '2026-11-05T06:00:00Z',
  end_at: '2026-11-05T08:00:00Z',
  duration_seconds: 5400,
  max_attempts: 2,
  total_score: '20.0',
  allow_review: true,
  shuffle_questions: false,
  shuffle_options: false,
  multiple_choice_mode: 'EXACT',
  pass_percentage: '60',
  grader_ids: [teacher.id],
  graders: [teacher],
  cancelled_at: null,
  cancelled_reason: null,
  content_revision: 1,
  grading_revision: 1,
  warnings: [],
  questions: [
    {
      id: 'question-1',
      source_question_id: null,
      type: 'SHORT_ANSWER',
      content: '说明拉格朗日中值定理成立的条件，并求出满足定理的 ξ。',
      options: [],
      standard_answer: '闭区间连续，开区间可导；由平均变化率求得 ξ = 2。',
      explanation: '定理条件 4 分，平均变化率 3 分，计算结果 3 分。',
      subject: '高等数学',
      knowledge_tags: [],
      difficulty: 'MEDIUM',
      score: '10.0',
    },
    {
      id: 'question-2',
      source_question_id: null,
      type: 'SHORT_ANSWER',
      content: '计算定积分并写出步骤。',
      options: [],
      standard_answer: '根据原函数计算。',
      explanation: null,
      subject: '高等数学',
      knowledge_tags: [],
      difficulty: 'MEDIUM',
      score: '10.0',
    },
  ],
}
function attempt(): StaffAttemptDetail {
  return {
    id: 'attempt-c3',
    exam_id: baseExam.id,
    exam_title: '高等数学 · 第一章测验',
    student,
    attempt_no: 1,
    status: 'SUBMITTED',
    submitted_at: '2026-11-05T08:00:00Z',
    effective_submitted_at: '2026-11-05T08:00:00Z',
    grading_status: 'GRADING',
    grading_revision: 1,
    final_score: null,
    graded_at: null,
    task: {
      id: 'task-c3',
      attempt_id: 'attempt-c3',
      assigned_teacher: teacher,
      status: 'IN_PROGRESS',
      grading_revision: 1,
      first_review_completed_at: null,
      completed_at: null,
      assigned_at: '2026-11-05T08:01:00Z',
      version: 1,
    },
    can_grade: true,
    can_reassign: false,
    results_published: false,
    questions: baseExam.questions.map((question, index) => ({
      id: question.id!,
      type: question.type,
      content: question.content,
      options: [],
      standard_answer: question.standard_answer,
      explanation: question.explanation,
      score: question.score,
      grading_revision: 1,
      can_grade: true,
      answer: {
        id: `answer-${index + 1}`,
        answer_data:
          index === 0
            ? '函数在闭区间连续且在开区间可导。由平均变化率为 4，得 2ξ = 4，所以 ξ = 2。'
            : '根据原函数求出结果。',
        version: 1,
        grading_status: index === 0 ? 'PENDING' : 'GRADED',
        grading_revision: 1,
        score: index === 0 ? null : '8.0',
        is_correct: null,
        grader_comment: index === 0 ? null : '计算正确，过程可更完整。',
        graded_by: index === 0 ? null : teacher.id,
        grading_method: index === 0 ? null : 'MANUAL',
        graded_at: index === 0 ? null : '2026-11-05T09:00:00Z',
      },
    })),
  }
}
function task(status: GradingTaskSummary['status'] = 'IN_PROGRESS'): GradingTaskSummary {
  return {
    ...attempt().task!,
    exam_id: baseExam.id,
    exam_title: '高等数学 · 第一章测验',
    student,
    attempt_no: 1,
    can_grade: true,
    can_reassign: false,
    status,
  }
}
async function mock(page: Page, role: 'TEACHER' | 'ADMIN' = 'TEACHER') {
  let exam = structuredClone(baseExam)
  let detail = attempt()
  const writes: Array<{ path: string; body: any }> = []
  const requests: string[] = []
  const unexpected: string[] = []
  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    if (!path.startsWith('/api/')) {
      await route.fallback()
      return
    }
    requests.push(`${request.method()} ${url.pathname}${url.search}`)
    if (request.method() !== 'GET') writes.push({ path, body: request.postDataJSON() })
    if (path === '/api/auth/me')
      return route.fulfill({ json: { user: { ...teacher, user_type: role } } })
    if (path === '/api/auth/csrf') return route.fulfill({ json: { csrf_token: 'staff-c3-token' } })
    if (path === '/api/staff/exams') {
      const status = url.searchParams.get('status')
      return route.fulfill({
        json: {
          items: status && status !== exam.status ? [] : [exam],
          total: status && status !== exam.status ? 0 : 23,
          page: Number(url.searchParams.get('page') || 1),
          page_size: Number(url.searchParams.get('page_size') || 20),
        },
      })
    }
    if (path === '/api/staff/exams/exam-c3') {
      if (request.method() === 'PUT')
        exam = { ...exam, ...request.postDataJSON(), version: exam.version + 1 }
      return route.fulfill({ json: exam })
    }
    if (path === '/api/staff/grading-tasks') {
      const status = url.searchParams.get('status') as GradingTaskSummary['status'] | null
      const totals = { PENDING: 7, IN_PROGRESS: 2, COMPLETED: 28, UNASSIGNED: 3, VOID: 0 }
      return route.fulfill({
        json: {
          items: [task(status || 'IN_PROGRESS')],
          total: status ? totals[status] : 37,
          page: 1,
          page_size: Number(url.searchParams.get('page_size') || 20),
        },
      })
    }
    if (path === '/api/staff/teachers' || path === '/api/admin/teachers')
      return route.fulfill({ json: { items: [teacher], total: 1 } })
    if (path === '/api/staff/questions') return route.fulfill({ json: { items: [], total: 0 } })
    if (path.endsWith('/participants')) return route.fulfill({ json: { items: [], total: 0 } })
    if (path.endsWith('/attempts') || path.endsWith('/final-results'))
      return route.fulfill({
        json: {
          items: [
            {
              ...detail,
              can_grade: false,
              task: { ...detail.task, assigned_teacher: null, status: 'UNASSIGNED' },
            },
          ],
          total: 1,
        },
      })
    if (path === '/api/staff/attempts/attempt-c3')
      return route.fulfill({
        json: { ...detail, can_grade: role === 'TEACHER', can_reassign: role === 'ADMIN' },
      })
    if (path.endsWith('/grade')) {
      const input = request.postDataJSON()
      const index = path.includes('answer-1') ? 0 : 1
      detail.questions[index]!.answer = {
        ...detail.questions[index]!.answer,
        score: input.score,
        grader_comment: input.comment,
        grading_status: 'GRADED',
        version: 2,
      }
      return route.fulfill({ json: detail })
    }
    if (path.endsWith('/history'))
      return route.fulfill({
        json: {
          items: [
            {
              id: 'history-c3',
              answer_id: 'answer-2',
              grading_revision: 1,
              actor: teacher,
              method: 'MANUAL',
              old_score: null,
              new_score: '8.0',
              old_is_correct: null,
              new_is_correct: null,
              old_comment: null,
              new_comment: '计算正确',
              reason: '首次人工评分。',
              created_at: '2026-11-05T09:00:00Z',
            },
          ],
        },
      })
    unexpected.push(`${request.method()} ${path}`)
    return route.fulfill({ status: 404, json: { detail: '未配置测试接口' } })
  })
  return {
    writes,
    requests,
    unexpected,
    setExam(value: Partial<Exam>) {
      exam = { ...exam, ...value }
    },
    setDetail(value: Partial<StaffAttemptDetail>) {
      detail = { ...detail, ...value }
    },
  }
}
async function capture(page: Page, info: TestInfo, name: string) {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(width)
    await page.screenshot({
      path: info.outputPath(`${name}-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    })
  }
}

test('教师首页按真实总数展示优先任务、统计和考试准备双栏', async ({ page }, info) => {
  const api = await mock(page)
  await page.goto('/home')
  await expect(page.getByRole('heading', { name: '还有 9 份答卷等待评分' })).toBeVisible()
  await expect(page.getByLabel('考试与阅卷统计')).toContainText('23')
  await expect(page.getByText('待阅与阅卷中共 9 份，优先继续已开始的答卷。')).toBeVisible()
  await expect(page.locator('.staff-home-grid')).toHaveCSS('grid-template-columns', /.+/)
  await capture(page, info, 'teacher-home')
  expect(api.unexpected).toEqual([])
})

test('管理员首页保留考试管理进度与人员入口，不提供人工评分入口', async ({ page }, info) => {
  const api = await mock(page, 'ADMIN')
  await page.goto('/home')
  await expect(page.getByText('人工评分由阅卷教师完成。', { exact: false })).toBeVisible()
  await expect(page.getByRole('link', { name: /进入阅卷工作台|进入阅卷|开始阅卷/ })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: '考试与阅卷进度' })).toBeVisible()
  await expect(page.locator('.staff-home-grid > .surface-panel')).toHaveCount(1)
  await expect(page.getByRole('heading', { name: '考试准备', exact: true })).toHaveCount(0)
  const progressBox = await page.locator('.staff-home-grid').boundingBox()
  const roleNoteBox = await page.locator('.staff-role-note').boundingBox()
  expect(roleNoteBox!.y).toBeGreaterThan(progressBox!.y + progressBox!.height)
  await capture(page, info, 'admin-home')
  expect(api.unexpected).toEqual([])
})

test('考试列表保留搜索分页并将状态筛选送到接口，按过滤结果显示总数', async ({ page }, info) => {
  const api = await mock(page)
  await page.goto('/staff/exams')
  await expect(page.getByRole('row').filter({ hasText: baseExam.title })).toContainText(
    '最多作答 2 次',
  )
  await capture(page, info, 'staff-exams')
  await page.getByRole('combobox', { name: '考试状态', exact: true }).click()
  await page.getByRole('option', { name: '结果已公布', exact: true }).click()
  await expect(page.getByText('共 0 场考试', { exact: true })).toBeVisible()
  expect(
    api.requests.some(
      (path) => path.includes('status=RESULTS_PUBLISHED') && path.includes('page=1'),
    ),
  ).toBeTruthy()
  expect(api.unexpected).toEqual([])
})

test('考试配置采用主表单和发布检查右栏，跨分区草稿与验证仍然有效', async ({ page }, info) => {
  const api = await mock(page)
  await page.goto('/staff/exams/exam-c3')
  await expect(page.getByRole('heading', { name: '发布检查' })).toBeVisible()
  await expect(page.locator('.exam-config-layout')).toHaveCSS('grid-template-columns', /300px$/)
  await capture(page, info, 'staff-detail')
  await page.getByLabel('考试说明', { exact: true }).fill('跨分区草稿内容')
  await expect(page.getByRole('button', { name: '发布考试 →' })).toBeDisabled()
  await page.getByRole('tab', { name: '题目快照', exact: true }).click()
  await page.getByRole('button', { name: '保存考试草稿', exact: true }).click()
  await expect(page.getByText('考试草稿已保存', { exact: true })).toBeVisible()
  expect(
    api.writes.find((write) => write.path === '/api/staff/exams/exam-c3')!.body.description,
  ).toBe('跨分区草稿内容')
  await page.getByRole('tab', { name: '考试配置', exact: true }).click()
  await expect(page.getByLabel('考试说明', { exact: true })).toHaveValue('跨分区草稿内容')
  expect(api.unexpected).toEqual([])
})

test('阅卷工作台统计来自任务总数，任务范围筛选与指定教师信息保留', async ({ page }, info) => {
  const api = await mock(page)
  await page.goto('/staff/grading-tasks')
  await expect(page.getByLabel('我的阅卷统计')).toContainText('37')
  await expect(page.getByRole('row').filter({ hasText: '林予安' })).toContainText(
    '整卷首阅尚未完成',
  )
  await capture(page, info, 'grading-tasks')
  await page.getByRole('button', { name: '已完成', exact: true }).click()
  await expect(page.getByRole('row').filter({ hasText: '林予安' })).toContainText('已完成')
  expect(api.requests.some((path) => path.includes('status=COMPLETED'))).toBeTruthy()
  expect(api.unexpected).toEqual([])
})

test('评分阅读主栏与评分右栏保留草稿保护、逐题保存、改分原因和历史', async ({ page }, info) => {
  const api = await mock(page)
  await page.goto('/staff/attempts/attempt-c3')
  await expect(page.getByRole('heading', { name: '本题评分', exact: true })).toBeVisible()
  await expect(page.getByRole('navigation', { name: '主导航' })).toHaveCount(0)
  await expect(page.locator('.grading-workspace')).toHaveCSS('grid-template-columns', /300px$/)
  await capture(page, info, 'staff-grade')
  await page.getByLabel('评分分值', { exact: true }).fill('6.5')
  await page.getByLabel('查看第 2 题', { exact: true }).click()
  await page.getByRole('button', { name: '继续评分', exact: true }).click()
  await expect(page.getByLabel('评分分值', { exact: true })).toHaveValue('6.5')
  await page.getByRole('button', { name: '保存本题评分', exact: true }).click()
  await expect(page.getByText('本题评分已保存。', { exact: true })).toBeVisible()
  await page.getByLabel('查看第 2 题', { exact: true }).click()
  await page.getByLabel('评分分值', { exact: true }).fill('9')
  await page.getByRole('button', { name: '保存本题评分', exact: true }).click()
  await expect(page.getByText('请填写改分原因。', { exact: true })).toBeVisible()
  await page.getByLabel('改分原因', { exact: true }).fill('复核计算过程，补计步骤分。')
  await page.getByRole('button', { name: '保存本题评分', exact: true }).click()
  await expect
    .poll(() => api.writes.filter((write) => write.path.endsWith('/grade')).length)
    .toBe(2)
  expect(api.writes.at(-1)!.body.reason).toBe('复核计算过程，补计步骤分。')
  await page.getByRole('button', { name: '查看本题评分历史', exact: true }).click()
  await expect(page.getByText('首次人工评分。', { exact: true })).toBeVisible()
  expect(api.unexpected).toEqual([])
})

test('管理员在考试详情查看进度和改派任务，不能进入评分工作区', async ({ page }, info) => {
  const api = await mock(page, 'ADMIN')
  api.setExam({ status: 'RELEASED' })
  await page.goto('/staff/exams/exam-c3')
  await page.getByRole('tab', { name: '阅卷进度与成绩', exact: true }).click()
  await expect(page.getByRole('button', { name: '改派任务', exact: true })).toBeVisible()
  await expect(page.getByRole('link', { name: /进入阅卷|查看答卷/ })).toHaveCount(0)
  await capture(page, info, 'admin-grading-progress')
  await page.getByRole('button', { name: '改派任务', exact: true }).click()
  await expect(page.getByRole('heading', { name: '改派阅卷任务', exact: true })).toBeVisible()
  await page.goto('/staff/attempts/attempt-c3')
  await expect(page).toHaveURL('/staff/exams')
  expect(api.writes.filter((write) => write.path.endsWith('/grade'))).toHaveLength(0)
  expect(api.unexpected).toEqual([])
})

test('保存参考稿截图用于逐页目检', async ({ page }, info) => {
  for (const name of ['staff-home', 'staff-exams', 'staff-detail', 'grading', 'grade']) {
    await page.goto(
      `file:///D:/codex_workspace/online-exam-system/design/ui-redesign/color.html?page=${name}`,
    )
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.screenshot({
      path: info.outputPath(`reference-${name}-1440.png`),
      fullPage: true,
      animations: 'disabled',
    })
  }
})
