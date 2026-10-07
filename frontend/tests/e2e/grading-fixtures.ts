import {
  expect,
  type APIRequestContext,
  type Browser,
  type BrowserContext,
  type Page,
} from '@playwright/test'

export const fixturePassword = 'Grading123!'
const temporaryPassword = 'Temporary123!'

export async function apiWrite(
  request: APIRequestContext,
  path: string,
  data: unknown,
  method = 'POST',
) {
  const { csrf_token } = await (await request.get('/api/auth/csrf')).json()
  const response = await request.fetch(`/api${path}`, {
    method,
    headers: { 'X-CSRF-Token': csrf_token },
    data,
  })
  expect(response.ok(), `${method} ${path} -> ${response.status()}`).toBeTruthy()
  return response.status() === 204 ? undefined : response.json()
}

export async function signedContext(
  browser: Browser,
  baseURL: string,
  loginName: string,
  password: string,
): Promise<BrowserContext> {
  const context = await browser.newContext({ baseURL })
  await apiWrite(context.request, '/auth/login', { login_name: loginName, password })
  return context
}

export async function gradingFixture(page: Page, browser: Browser, endsInSeconds = 3600) {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const teachers = []
  for (let index = 0; index < 2; index += 1) {
    const loginName = `I4T${suffix}${index}`
    const { user } = await apiWrite(page.request, '/admin/teachers', {
      teacher_no: loginName,
      real_name: index === 0 ? '首阅测试教师' : '共享改分教师',
      email: `${loginName}@example.com`,
      phone_number: '13800000000',
      temporary_password: temporaryPassword,
    })
    const context = await signedContext(
      browser,
      new URL(page.url()).origin,
      loginName,
      temporaryPassword,
    )
    await apiWrite(
      context.request,
      '/auth/password',
      { current_password: temporaryPassword, new_password: fixturePassword },
      'PUT',
    )
    await context.close()
    teachers.push({ id: user.id as string, loginName })
  }
  const studentLogin = `I4S${suffix}`
  const { user: student } = await apiWrite(page.request, '/auth/register', {
    student_no: studentLogin,
    real_name: '阅卷测试学生',
    email: `${studentLogin}@example.com`,
    phone_number: '13900000000',
    password: fixturePassword,
  })
  const reviews = await (await page.request.get(`/api/staff/reviews?q=${studentLogin}`)).json()
  await apiWrite(page.request, `/staff/reviews/${reviews.items[0].id}/decision`, {
    decision: 'APPROVED',
  })
  const questions = []
  for (let index = 0; index < 3; index += 1) {
    const type = index === 2 ? 'TRUE_FALSE' : 'SHORT_ANSWER'
    const question = await apiWrite(page.request, '/staff/questions', {
      type,
      content: `${index === 2 ? '判断概念' : `论述问题${index + 1}`} ${suffix}`,
      options: [],
      standard_answer: index === 2 ? false : `评分依据${index + 1}`,
      explanation: '根据核心概念与完整论证评分。',
      subject: '人工阅卷测试',
      knowledge_tags: [],
      difficulty: 'MEDIUM',
    })
    questions.push(question)
  }
  const paper = await apiWrite(page.request, '/staff/papers', {
    title: `人工阅卷试卷 ${suffix}`,
    questions: questions.map((question) => ({ question_id: question.id, score: '5.0' })),
  })
  const exam = await apiWrite(page.request, '/staff/exams', {
    title: `人工阅卷考试 ${suffix}`,
    source_paper_id: paper.id,
    audience_type: 'PUBLIC',
  })
  const configured = await apiWrite(
    page.request,
    `/staff/exams/${exam.id}`,
    {
      ...exam,
      start_at: new Date(Date.now() - 60_000).toISOString(),
      end_at: new Date(Date.now() + endsInSeconds * 1000).toISOString(),
      duration_seconds: Math.min(1800, endsInSeconds),
      max_attempts: 2,
      grader_ids: [teachers[0]!.id],
    },
    'PUT',
  )
  await apiWrite(page.request, `/staff/exams/${exam.id}/publish`, { version: configured.version })
  const studentContext = await signedContext(
    browser,
    new URL(page.url()).origin,
    studentLogin,
    fixturePassword,
  )
  try {
    const attempt = await submitAttempt(studentContext.request, exam.id, [
      '第一题学生论证',
      '第二题学生论证',
      false,
    ])
    return {
      exam: { id: exam.id as string, title: exam.title as string },
      attemptId: attempt.id as string,
      teachers,
      student: { id: student.id as string, loginName: studentLogin },
      endAt: configured.end_at as string,
    }
  } finally {
    await studentContext.close()
  }
}

export async function submitAttempt(
  request: APIRequestContext,
  examId: string,
  values: (string | boolean | null)[],
) {
  const attempt = await apiWrite(request, `/student/exams/${examId}/attempts`, {})
  const active = await apiWrite(request, `/student/attempts/${attempt.id}/activate`, {
    expected_generation: 0,
  })
  for (let index = 0; index < active.questions.length; index += 1) {
    const answer = active.questions[index].answer
    await apiWrite(
      request,
      `/student/attempts/${attempt.id}/answers/${answer.id}`,
      {
        page_token: active.page_token,
        token_generation: active.token_generation,
        version: answer.version,
        answer_data: values[index],
      },
      'PUT',
    )
  }
  return apiWrite(request, `/student/attempts/${attempt.id}/submit`, {
    page_token: active.page_token,
    token_generation: active.token_generation,
    confirm_unanswered: true,
  })
}

export async function waitForTask(page: Page, examId: string, attemptId: string): Promise<void> {
  await expect
    .poll(
      async () => {
        await apiWrite(page.request, `/staff/exams/${examId}/grading/refresh`, {})
        const response = await page.request.get(`/api/staff/attempts/${attemptId}`)
        if (!response.ok()) return null
        return (await response.json()).task?.assigned_teacher?.id ?? null
      },
      { timeout: 20_000, intervals: [500, 1000] },
    )
    .not.toBeNull()
}

export async function gradeWholeAttempt(
  request: APIRequestContext,
  attemptId: string,
  scores = ['4.0', '4.0'],
) {
  let detail = await (await request.get(`/api/staff/attempts/${attemptId}`)).json()
  const answerIds = detail.questions
    .filter((question: { type: string }) => question.type === 'SHORT_ANSWER')
    .map((question: { answer: { id: string } }) => question.answer.id)
  for (let index = 0; index < answerIds.length; index += 1) {
    const question = detail.questions.find(
      (item: { answer: { id: string } }) => item.answer.id === answerIds[index],
    )
    detail = await apiWrite(request, `/staff/answers/${question.answer.id}/grade`, {
      version: question.answer.version,
      grading_revision: question.grading_revision,
      score: scores[index],
      comment: null,
      reason: question.answer.score === null ? null : '按更正后的评分依据重新审核。',
    })
  }
  return detail
}
