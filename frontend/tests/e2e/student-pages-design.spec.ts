import { expect, test, type Page, type TestInfo } from '@playwright/test'
import { readFile } from 'node:fs/promises'

test.setTimeout(60000)

// 接口快照只用于界面回归，页面运行时仍全部读取服务端数据。
const now = '2026-11-03T06:00:00Z'
const user = {
  id: 'student-pages',
  login_name: '20260101',
  real_name: '林同学',
  user_type: 'STUDENT',
  status: 'ACTIVATED',
  must_change_password: false,
}
const examBase = {
  description: '请在截止前确认服务器保存状态。',
  audience_type: 'PUBLIC',
  status: 'RELEASED',
  start_at: '2026-11-03T05:00:00Z',
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
  can_start: true,
  unavailable_reason: null,
}
const exams = [
  {
    ...examBase,
    id: 'current',
    title: '高等数学 · 期中测验',
    current_attempt_id: 'attempt',
    current_attempt_status: 'IN_PROGRESS',
    used_attempts: 1,
    remaining_attempts: 1,
  },
  { ...examBase, id: 'available', title: '线性代数 · 第二章单元测验', duration_seconds: 2700 },
  {
    ...examBase,
    id: 'upcoming',
    title: '高等数学 · 积分专项练习',
    start_at: '2026-11-05T06:00:00Z',
    end_at: '2026-11-05T08:00:00Z',
    can_start: false,
  },
  {
    ...examBase,
    id: 'ended',
    title: '线性代数 · 第一章测验',
    start_at: '2026-10-28T06:00:00Z',
    end_at: '2026-10-28T08:00:00Z',
    can_start: false,
  },
]
const question = {
  id: 'question-1',
  order_no: 1,
  display_order: 1,
  type: 'SINGLE_CHOICE',
  content: '设矩阵 A 为三阶方阵，且 |A| = 2，则 |2A| 的值为多少？',
  options: [
    { id: 'a', content: '4' },
    { id: 'b', content: '8' },
    { id: 'c', content: '16' },
    { id: 'd', content: '32' },
  ],
  standard_answer: ['c'],
  explanation: 'n 阶矩阵满足 |kA| = kⁿ|A|。因此 |2A| = 2³ × 2 = 16。',
  subject: '线性代数',
  knowledge_tags: ['行列式的性质', '矩阵运算'],
  difficulty: 'MEDIUM',
  score: '4',
  answer: {
    id: 'answer-1',
    answer_data: ['b'],
    grading_status: 'GRADED',
    score: '0',
    is_correct: false,
    grader_comment: null,
  },
}
const questions = [
  question,
  {
    ...question,
    id: 'question-2',
    display_order: 2,
    content: '计算 1 + 1 的值。',
    standard_answer: ['b'],
    answer: { ...question.answer, id: 'answer-2', score: '4', is_correct: true },
  },
]
const result = {
  exam_id: 'result',
  title: '线性代数 · 第一章测验',
  exam_status: 'RESULTS_PUBLISHED',
  result_state: 'PUBLISHED',
  participant_status: 'ACTIVE',
  end_at: '2026-10-28T08:00:00Z',
  total_score: '100',
  allow_review: true,
  can_review: true,
  attempts_count: 1,
  final_attempt_id: 'review',
  final_attempt_no: 1,
  grading_status: 'GRADED',
  final_score: '86',
  submitted_at: '2026-10-28T06:42:00Z',
  attempts: [
    {
      id: 'review',
      attempt_no: 1,
      status: 'SUBMITTED',
      started_at: now,
      submitted_at: '2026-10-28T06:42:00Z',
      grading_status: 'GRADED',
      final_score: '86',
      can_review: true,
    },
  ],
}
const mistake = {
  answer_id: 'answer-1',
  attempt_id: 'review',
  attempt_no: 1,
  exam_id: 'result',
  exam_title: result.title,
  submitted_at: result.submitted_at,
  question_id: question.id,
  type: question.type,
  subject: question.subject,
  knowledge_tags: question.knowledge_tags,
  content: question.content,
  score: '0',
  full_score: '4',
  note: '行列式整体乘系数时，需要按矩阵阶数取幂。',
  mastered: false,
  question,
}

async function identity(page: Page) {
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: { user } }))
  await page.route('**/api/auth/csrf', (route) =>
    route.fulfill({ json: { csrf_token: 'test-csrf' } }),
  )
}
async function capture(page: Page, info: TestInfo, name: string) {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(width)
    for (const chart of await page.locator('.analytics-chart').all()) {
      await expect(chart.locator('svg')).toBeVisible()
      await expect.poll(() => chart.locator('svg path').count()).toBeGreaterThan(0)
    }
    await page.screenshot({
      path: info.outputPath(`${name}-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    })
  }
  await page.setViewportSize({ width: 1440, height: 1000 })
}

test('我的考试采用状态页签和独立时间列，筛选只显示真实当前页数据', async ({ page }, info) => {
  await identity(page)
  await page.route('**/api/student/exams?**', (route) =>
    route.fulfill({ json: { items: exams, total: 4, page: 1, page_size: 20 } }),
  )
  await page.goto('/student/exams')
  await expect(page.locator('.student-exam-row')).toHaveCount(4)
  await capture(page, info, 'exams')
  await page.getByRole('tab', { name: '进行中' }).click()
  await expect(page.locator('.student-exam-row')).toHaveCount(1)
  await expect(page.locator('.student-exam-row')).toContainText(exams[0]!.title)
  await page.getByRole('tab', { name: '未开始' }).click()
  await expect(page.locator('.student-exam-row')).toContainText(exams[2]!.title)
})

test('考试历史与成绩详情保持列表层次、右侧最终成绩和回看权限', async ({ page }, info) => {
  await identity(page)
  let published = true
  await page.route('**/api/student/results?**', (route) =>
    route.fulfill({
      json: {
        items: [
          result,
          {
            ...result,
            exam_id: 'pending',
            title: '高等数学 · 期中测验',
            result_state: 'NOT_PUBLISHED',
            final_score: null,
          },
        ],
        total: 2,
        page: 1,
        page_size: 20,
      },
    }),
  )
  await page.route('**/api/student/results/result', (route) =>
    route.fulfill({
      json: published
        ? result
        : {
            ...result,
            result_state: 'NOT_PUBLISHED',
            can_review: false,
            final_score: null,
            attempts: result.attempts.map((item) => ({
              ...item,
              can_review: false,
              final_score: null,
            })),
          },
    }),
  )
  await page.goto('/student/results')
  await expect(page.locator('.history-table tbody tr')).toHaveCount(2)
  await expect(page.locator('.history-table tbody tr').nth(1)).toContainText('—')
  await capture(page, info, 'results')
  await page.goto('/student/results/result')
  await expect(page.getByRole('link', { name: '回看本次答卷 →' })).toBeVisible()
  await expect(page.locator('.result-aside')).toContainText('86')
  await capture(page, info, 'result-detail')
  published = false
  await page.getByRole('button', { name: '刷新结果', exact: true }).click()
  await expect(page.locator('.result-aside .result-score')).toHaveText('—')
  await expect(page.getByRole('link', { name: '回看本次答卷 →' })).toHaveCount(0)
  await capture(page, info, 'result-unpublished')
})

test('答卷回看采用逐题与侧栏导航，未满分筛选和撤回清空仍有效', async ({ page }, info) => {
  await identity(page)
  let revoked = false
  await page.route('**/api/student/attempts/review/review', (route) =>
    route.fulfill(
      revoked
        ? {
            status: 404,
            json: { detail: { code: 'REVIEW_NOT_AVAILABLE', message: '本次答卷暂不可回看' } },
          }
        : {
            json: {
              id: 'review',
              exam_id: 'result',
              exam_title: result.title,
              attempt_no: 1,
              submitted_at: result.submitted_at,
              total_score: '100',
              final_score: '86',
              questions,
            },
          },
    ),
  )
  await page.goto('/student/attempts/review/review')
  await expect(page.locator('.review-question')).toHaveCount(1, { timeout: 15000 })
  await capture(page, info, 'review')
  await page.getByRole('button', { name: '回看第 2 题', exact: true }).click()
  await expect(page.locator('.review-question-copy')).toContainText('1 + 1')
  await page.getByLabel('仅看未满分题目').check()
  await expect(
    page.getByRole('navigation', { name: '回看题目导航' }).locator('button'),
  ).toHaveCount(1)
  revoked = true
  await page.getByRole('button', { name: '刷新答卷', exact: true }).click()
  await expect(page.locator('.review-question')).toHaveCount(0)
  await expect(page.getByText('本次答卷暂不可回看')).toBeVisible()
})

test('错题采用表格列表与笔记主栏、掌握情况侧栏，标记真实保存', async ({ page }, info) => {
  await identity(page)
  await page.route('**/api/student/mistakes?**', (route) =>
    route.fulfill({ json: { items: [mistake], total: 1, page: 1, page_size: 20 } }),
  )
  await page.route('**/api/student/mistakes/answer-1', (route) => route.fulfill({ json: mistake }))
  let saved: unknown
  await page.route('**/api/student/mistakes/answer-1/annotation', (route) => {
    saved = route.request().postDataJSON()
    return route.fulfill({ json: saved })
  })
  await page.goto('/student/mistakes')
  await expect(page.locator('.mistakes-table tbody tr')).toHaveCount(1)
  await capture(page, info, 'mistakes')
  await page.getByRole('link', { name: '复习 →', exact: true }).click()
  await expect(page.getByRole('heading', { name: '我的复习笔记' })).toBeVisible()
  await capture(page, info, 'mistake-detail')
  const completeOptions = page.locator('details.review-options-container')
  await expect(completeOptions).not.toHaveAttribute('open', '')
  await completeOptions.locator('summary').click()
  await expect(completeOptions.locator('.review-options > div')).toHaveCount(4)
  await expect(completeOptions.getByText('32', { exact: true })).toBeVisible()
  await page.getByLabel('学习备注').fill('需要按矩阵阶数取幂。')
  await page.getByLabel('已掌握本题').check()
  await page.getByRole('button', { name: '保存学习标记', exact: true }).click()
  await expect.poll(() => saved).toEqual({ note: '需要按矩阵阶数取幂。', mastered: true })
  await expect(page.getByText('学习标记已保存。', { exact: true })).toBeVisible()
})

test('学习分析四项统计读取真实样本和错题总数，首排趋势与知识点并列', async ({ page }, info) => {
  await identity(page)
  await page.route('**/api/student/analytics', (route) =>
    route.fulfill({
      json: {
        sample_exam_count: 3,
        review_exam_count: 2,
        trend: [
          {
            exam_id: '1',
            title: '第一次考试',
            end_at: '2026-10-01T06:00:00Z',
            submitted_at: now,
            final_score: '72',
            total_score: '100',
            score_rate: '0.72',
          },
          {
            exam_id: '2',
            title: '第二次考试',
            end_at: '2026-10-15T06:00:00Z',
            submitted_at: now,
            final_score: '86',
            total_score: '100',
            score_rate: '0.86',
          },
          {
            exam_id: '3',
            title: '第三次考试',
            end_at: '2026-10-28T06:00:00Z',
            submitted_at: now,
            final_score: '88',
            total_score: '100',
            score_rate: '0.88',
          },
        ],
        type_performance: [
          {
            type: 'SINGLE_CHOICE',
            answer_count: 10,
            score_sum: '32',
            full_score_sum: '40',
            score_rate: '0.8',
          },
        ],
        knowledge_mistakes: [
          { knowledge_tag: '中值定理', count: 5 },
          { knowledge_tag: '行列式', count: 4 },
          { knowledge_tag: '连续与可导', count: 3 },
        ],
        knowledge_note: '按错误作答记录统计。',
      },
    }),
  )
  await page.route('**/api/student/mistakes?**', (route) =>
    route.fulfill({
      json: {
        items: [],
        total: new URL(route.request().url()).searchParams.get('mastered') === 'true' ? 8 : 12,
        page: 1,
        page_size: 1,
      },
    }),
  )
  await page.goto('/student/analytics')
  await expect(page.getByRole('definition')).toHaveCount(4)
  await expect(page.getByLabel('学习概况')).toContainText('82.0')
  await expect(page.getByLabel('学习概况')).toContainText('12')
  await expect(page.getByLabel('学习概况')).toContainText('8')
  await expect(page.getByRole('img', { name: '最终得分率趋势图', exact: true })).toBeVisible()
  await capture(page, info, 'analytics')
})

test('交卷完成展示真实提交类型与后续入口', async ({ page }, info) => {
  await identity(page)
  await page.route('**/api/student/attempts/submitted', (route) =>
    route.fulfill({
      json: {
        id: 'submitted',
        exam_id: 'result',
        exam_title: result.title,
        attempt_no: 1,
        status: 'SUBMITTED',
        started_at: now,
        deadline_at: now,
        submitted_at: now,
        effective_submitted_at: now,
        submission_type: 'MANUAL',
        grading_status: 'GRADING',
        server_now: now,
        version: 2,
        token_generation: 0,
        questions: [],
      },
    }),
  )
  await page.goto('/student/attempts/submitted')
  await expect(page.getByRole('heading', { name: '本次作答已提交' })).toBeVisible()
  await expect(page.getByText('手动交卷成功', { exact: true })).toBeVisible()
  await capture(page, info, 'submitted')
})

test('生成本地设计稿逐页参考截图供目检', async ({ page }, info) => {
  const html = await readFile(
    new URL('../../../design/ui-redesign/color.html', import.meta.url),
    'utf8',
  )
  await page.route('http://c3-reference.local/**', (route) =>
    route.fulfill({ contentType: 'text/html', body: html }),
  )
  for (const name of [
    'student-exams',
    'student-detail',
    'attempt',
    'submitted',
    'results',
    'result-detail',
    'review',
    'mistakes',
    'mistake-detail',
    'analytics',
  ]) {
    await page.goto(`http://c3-reference.local/?page=${name}&role=student&scene=default`)
    await capture(page, info, `reference-${name}`)
  }
})
