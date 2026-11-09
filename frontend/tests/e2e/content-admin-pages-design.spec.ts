import { expect, test, type Page, type TestInfo } from '@playwright/test'
import type { Question } from '../../src/api/questions'
import type { Paper } from '../../src/api/papers'

test.setTimeout(60_000)

const teacher = {
  id: 'teacher-1',
  login_name: 'T2026008',
  real_name: '陈老师',
  user_type: 'TEACHER',
  status: 'ACTIVATED',
  email: 'teacher@example.test',
  phone_number: '13900000000',
  must_change_password: false,
  created_at: '2026-11-03T08:00:00Z',
}
const questions: Question[] = [
  {
    id: 'q-2401',
    creator_id: teacher.id,
    type: 'SINGLE_CHOICE',
    content: '设函数 f(x) 在 x = 0 处可导，求导数定义对应的极限。',
    options: [
      { id: 'A', content: '2' },
      { id: 'B', content: '6' },
    ],
    standard_answer: ['B'],
    explanation: '由导数定义计算。',
    subject: '高等数学',
    knowledge_tags: ['导数的定义'],
    difficulty: 'EASY',
    status: 'ACTIVE',
    version: 1,
    created_at: '2026-11-03T08:00:00Z',
    updated_at: '2026-11-03T08:00:00Z',
  },
  {
    id: 'q-2402',
    creator_id: teacher.id,
    type: 'TRUE_FALSE',
    content: '函数可导一定连续。',
    options: [],
    standard_answer: true,
    explanation: '可导是连续的充分条件。',
    subject: '高等数学',
    knowledge_tags: ['连续与可导'],
    difficulty: 'MEDIUM',
    status: 'ACTIVE',
    version: 1,
    created_at: '2026-11-03T08:00:00Z',
    updated_at: '2026-11-03T08:00:00Z',
  },
]
const basePaper: Paper = {
  id: 'paper-1',
  creator_id: teacher.id,
  title: '高等数学 · 期中标准卷 A',
  description: '单选、判断 · 导数与连续',
  status: 'ACTIVE',
  version: 1,
  total_score: '10.0',
  question_count: 2,
  questions: questions.map((question, index) => ({
    id: `pq-${index}`,
    question_id: question.id,
    order_no: index + 1,
    score: '5.0',
    question,
  })),
}

async function identity(page: Page): Promise<void> {
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({
      json: { user: { ...teacher, id: 'admin-1', user_type: 'ADMIN', real_name: '管理员' } },
    }),
  )
  await page.route('**/api/auth/csrf', (route) =>
    route.fulfill({ json: { csrf_token: 'c3-content-token' } }),
  )
}

async function capture(page: Page, info: TestInfo, name: string): Promise<void> {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 })
    await expect
      .poll(() => page.evaluate(() => document.documentElement.scrollWidth))
      .toBeLessThanOrEqual(width)
    await page.screenshot({ path: info.outputPath(`${name}-${width}.png`), fullPage: true })
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
}

test('题库与题编辑落实六列表格、属性侧栏，筛选保存与放弃修改保留', async ({ page }, info) => {
  await identity(page)
  let savedContent = ''
  await page.route('**/api/staff/questions?**', (route) => {
    const q = new URL(route.request().url()).searchParams.get('q') || ''
    return route.fulfill({
      json: {
        items: questions.filter((item) => item.content.includes(q)),
        total: q ? 1 : 2,
        page: 1,
        page_size: 20,
      },
    })
  })
  await page.route('**/api/staff/questions/q-2401', (route) => {
    if (route.request().method() === 'PUT') savedContent = route.request().postDataJSON().content
    return route.fulfill({
      json: { ...questions[0], content: savedContent || questions[0]!.content },
    })
  })
  await page.goto('/staff/questions')
  await expect(page.getByRole('columnheader')).toHaveText([
    '题目',
    '科目 / 知识点',
    '题型',
    '难度',
    '状态',
    '操作',
  ])
  await capture(page, info, 'questions')
  await page.getByRole('button', { name: '编辑', exact: true }).first().click()
  await expect(page.getByRole('heading', { name: '题目属性' })).toBeVisible()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await capture(page, info, 'question-edit')
  await page.getByLabel('题干', { exact: true }).fill('已修改的真实草稿')
  await page.getByRole('button', { name: '← 返回题库' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: '继续编辑', exact: true }).click()
  await page.getByRole('button', { name: '保存题目', exact: true }).click()
  await expect(page.getByRole('heading', { name: '共享题库', exact: true })).toBeVisible()
  expect(savedContent).toBe('已修改的真实草稿')
  await page.getByLabel('搜索题目').fill('可导')
  await page.getByRole('button', { name: '查询题目', exact: true }).click()
  await expect(page.locator('tbody tr')).toHaveCount(2)
})

test('共享试卷和组卷采用题目主栏与概况侧栏，添加排序设分保存保持业务值', async ({ page }, info) => {
  await identity(page)
  let paper = structuredClone(basePaper)
  await page.route('**/api/staff/papers?**', (route) =>
    route.fulfill({ json: { items: [paper], total: 1, page: 1, page_size: 20 } }),
  )
  await page.route('**/api/staff/papers/paper-1', (route) => {
    if (route.request().method() === 'PUT') {
      const input = route.request().postDataJSON()
      paper = {
        ...paper,
        title: input.title,
        questions: input.questions.map(
          (row: { question_id: string; score: string }, index: number) => ({
            id: `pq-${index}`,
            question_id: row.question_id,
            score: row.score,
            order_no: index + 1,
            question: questions.find((question) => question.id === row.question_id)!,
          }),
        ),
      }
    }
    return route.fulfill({ json: paper })
  })
  await page.route('**/api/staff/questions?**', (route) =>
    route.fulfill({ json: { items: questions, total: 2, page: 1, page_size: 10 } }),
  )
  await page.goto('/staff/papers')
  await expect(page.getByText(basePaper.title, { exact: true })).toBeVisible()
  await capture(page, info, 'papers')
  await page.getByRole('button', { name: '编辑组卷', exact: true }).click()
  await expect(page.getByRole('heading', { name: '试卷概况' })).toBeVisible()
  await capture(page, info, 'paper-edit')
  await page.getByLabel('第 1 题分值', { exact: true }).fill('2.5')
  await expect(page.getByRole('status', { name: '试卷分值汇总' })).toHaveText(
    '2 道题 · 总分 7.5 分',
  )
  await page.getByRole('button', { name: '上移第 2 题' }).click()
  await page.getByRole('button', { name: '从题库添加', exact: true }).click()
  await expect(
    page.getByRole('dialog').getByRole('button', { name: '已加入', exact: true }),
  ).toHaveCount(2)
  await page.getByRole('dialog').getByRole('button', { name: '完成选题', exact: true }).click()
  await page.getByRole('button', { name: '保存试卷', exact: true }).first().click()
  await expect(page.getByRole('heading', { name: '共享试卷', exact: true })).toBeVisible()
  expect(paper.questions.map((item) => item.question_id)).toEqual(['q-2402', 'q-2401'])
  expect(paper.questions[1]!.score).toBe('2.5')
})

test('账号和教学班采用独立过滤区与记录表格，管理弹窗完整保留', async ({ page }, info) => {
  await identity(page)
  const teachingClass = {
    id: 'class-1',
    name: '计算机 2401 班',
    description: '2024 级软件工程',
    status: 'ACTIVE',
    teachers: [teacher],
    students: [],
    student_count: 48,
    created_at: '2026-10-01T08:00:00Z',
    updated_at: '2026-11-03T08:00:00Z',
  }
  await page.route('**/api/admin/users?**', (route) =>
    route.fulfill({ json: { items: [teacher], total: 1, page: 1, page_size: 20 } }),
  )
  await page.route('**/api/classes?**', (route) =>
    route.fulfill({ json: { items: [teachingClass], total: 1, page: 1, page_size: 20 } }),
  )
  await page.route('**/api/classes/class-1', (route) =>
    route.fulfill({ json: { class_info: teachingClass } }),
  )
  await page.route('**/api/staff/students?**', (route) =>
    route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20 } }),
  )
  await page.goto('/admin/accounts')
  await expect(page.getByText('陈老师', { exact: true })).toBeVisible()
  await capture(page, info, 'accounts')
  await page.getByRole('button', { name: '更正', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: '取消', exact: true }).click()
  await page.goto('/classes')
  await expect(page.getByText(teachingClass.name, { exact: true })).toBeVisible()
  await capture(page, info, 'classes')
  await page.getByRole('button', { name: '成员管理', exact: true }).click()
  await expect(page.getByRole('heading', { name: '当前成员', exact: true })).toBeVisible()
})

test('审核先呈现资料核验，日志按时间级别模块记录分列并保留详情及筛选', async ({ page }, info) => {
  await identity(page)
  const review = {
    id: 'review-1',
    status: 'PENDING',
    reason: null,
    submitted_profile: {
      student_no: '2026240106',
      real_name: '许嘉宁',
      email: 'student@example.test',
      phone_number: '13800000002',
    },
    submitted_at: '2026-11-03T02:26:00Z',
    reviewed_at: null,
    reviewer_id: null,
    user: { ...teacher, id: 'student-1', user_type: 'STUDENT' },
  }
  await page.route('**/api/staff/reviews?**', (route) =>
    route.fulfill({ json: { items: [review], total: 1, page: 1, page_size: 20 } }),
  )
  await page.route('**/api/staff/reviews/review-1/decision', (route) => {
    review.status = route.request().postDataJSON().decision
    return route.fulfill({ json: { application: review } })
  })
  await page.goto('/staff/reviews')
  await expect(page.getByRole('button', { name: '审核资料', exact: true })).toBeVisible()
  await capture(page, info, 'reviews')
  await page.getByRole('button', { name: '审核资料', exact: true }).click()
  await expect(page.getByRole('dialog')).toContainText('student@example.test')
  await page.getByRole('button', { name: '核验通过', exact: true }).click()
  await expect(page.getByRole('button', { name: '查看资料', exact: true })).toBeVisible()
  await page.route('**/api/admin/logs/runtime?**', (route) => {
    const query = new URL(route.request().url()).searchParams.get('q')
    return route.fulfill({
      json: {
        items: query
          ? []
          : [
              {
                id: 'log-1',
                cursor: 'cursor-1',
                timestamp: '2026-11-03T07:02:18Z',
                formatted: '2026-11-03T07:02:18Z INFO attempts 答案已保存',
                level: 'INFO',
                module: '作答',
                task: 'save_answer',
                message: 'ATT-0042 答案已保存 · 版本 12',
                correlation_id: 'request-1',
              },
            ],
        latest_cursor: 'cursor-1',
        next_before: null,
        has_more: false,
      },
    })
  })
  await page.route('**/api/admin/logs/audit?**', (route) =>
    route.fulfill({ json: { items: [], latest_cursor: null, next_before: null, has_more: false } }),
  )
  await page.goto('/admin/logs')
  await expect(page.locator('.log-entry')).toHaveCount(1)
  await page.getByLabel('自动刷新').uncheck()
  await capture(page, info, 'logs')
  await page.locator('.log-entry summary').click()
  await expect(page.locator('.log-entry-detail')).toContainText('request-1')
  await page.getByLabel('关键词', { exact: true }).fill('没有此记录')
  await page.getByRole('button', { name: '应用筛选', exact: true }).click()
  await expect(page.getByText('当前筛选下暂无日志', { exact: true })).toBeVisible()
  await page.getByRole('tab', { name: '操作审计', exact: true }).click()
  await expect(page.getByLabel('操作者 ID', { exact: true })).toBeVisible()
})
