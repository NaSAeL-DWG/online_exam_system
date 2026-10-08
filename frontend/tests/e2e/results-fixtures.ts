import { expect, type Browser, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { apiWrite, fixturePassword, signedContext, submitAttempt } from './grading-fixtures'

/** 使用真实公开接口建立两次作答，第一份部分得分，最后一份满分。 */
export async function resultsFixture(
  page: Page,
  browser: Browser,
  options: { twoAttempts?: boolean; allowReview?: boolean; endsInSeconds?: number } = {},
) {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const a = randomUUID()
  const b = randomUUID()
  const c = randomUUID()
  const loginName = `I5S${suffix}`
  const { user } = await apiWrite(page.request, '/auth/register', {
    student_no: loginName,
    real_name: '成绩学习测试学生',
    email: `${loginName}@example.com`,
    phone_number: '13900000000',
    password: fixturePassword,
  })
  const reviews = await (await page.request.get(`/api/staff/reviews?q=${loginName}`)).json()
  await apiWrite(page.request, `/staff/reviews/${reviews.items[0].id}/decision`, {
    decision: 'APPROVED',
  })
  const drafts = [
    { type: 'TRUE_FALSE', options: [], standard_answer: true },
    {
      type: 'SINGLE_CHOICE',
      options: [
        { id: a, content: '第一选项' },
        { id: b, content: '第二选项' },
      ],
      standard_answer: [b],
    },
    {
      type: 'MULTIPLE_CHOICE',
      options: [
        { id: a, content: '甲' },
        { id: b, content: '乙' },
        { id: c, content: '丙' },
      ],
      standard_answer: [a, b],
    },
  ]
  const questions = []
  for (const [index, draft] of drafts.entries()) {
    questions.push(
      await apiWrite(page.request, '/staff/questions', {
        ...draft,
        content: `独立成绩快照题${index + 1} ${suffix}`,
        explanation: `快照解析${index + 1}：依据定义与计算过程。`,
        subject: '结果学习测试',
        knowledge_tags: ['函数', '代数'],
        difficulty: 'MEDIUM',
      }),
    )
  }
  const paper = await apiWrite(page.request, '/staff/papers', {
    title: `结果学习试卷 ${suffix}`,
    questions: questions.map((question) => ({ question_id: question.id, score: '5.0' })),
  })
  const exam = await apiWrite(page.request, '/staff/exams', {
    title: `结果学习考试 ${suffix}`,
    source_paper_id: paper.id,
    audience_type: 'PUBLIC',
  })
  const configured = await apiWrite(
    page.request,
    `/staff/exams/${exam.id}`,
    {
      ...exam,
      start_at: new Date(Date.now() - 60_000).toISOString(),
      end_at: new Date(Date.now() + (options.endsInSeconds ?? 5) * 1000).toISOString(),
      duration_seconds: options.endsInSeconds ?? 5,
      max_attempts: 2,
      allow_review: options.allowReview ?? true,
      multiple_choice_mode: 'PARTIAL',
    },
    'PUT',
  )
  await apiWrite(page.request, `/staff/exams/${exam.id}/publish`, { version: configured.version })
  const context = await signedContext(
    browser,
    new URL(page.url()).origin,
    loginName,
    fixturePassword,
  )
  const first = await submitAttempt(context.request, exam.id, [false, [a], [a]])
  let last = first
  if (options.twoAttempts) last = await submitAttempt(context.request, exam.id, [true, [b], [a, b]])
  await expect
    .poll(async () => {
      await apiWrite(page.request, `/staff/exams/${exam.id}/grading/refresh`, {})
      return (await (await page.request.get(`/api/staff/attempts/${last.id}`)).json())
        .grading_status
    })
    .toBe('GRADED')
  return {
    exam: { id: exam.id as string, title: exam.title as string },
    firstId: first.id as string,
    lastId: last.id as string,
    context,
    student: { id: user.id as string, loginName },
    endAt: configured.end_at as string,
    questions,
  }
}

export async function publishFixture(page: Page, fixture: { exam: { id: string }; endAt: string }) {
  await expect.poll(() => Date.now() >= Date.parse(fixture.endAt), { timeout: 15_000 }).toBe(true)
  const exam = await (await page.request.get(`/api/staff/exams/${fixture.exam.id}`)).json()
  return apiWrite(page.request, `/staff/exams/${fixture.exam.id}/publish-results`, {
    version: exam.version,
  })
}
