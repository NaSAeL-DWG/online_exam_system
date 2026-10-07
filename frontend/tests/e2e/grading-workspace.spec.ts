import { expect, test, type Page } from '@playwright/test'
import {
  apiWrite,
  fixturePassword,
  gradeWholeAttempt,
  gradingFixture,
  signedContext,
  submitAttempt,
  waitForTask,
} from './grading-fixtures'

async function createPublishedExam(page: Page): Promise<{ id: string; title: string }> {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const { csrf_token } = await (await page.request.get('/api/auth/csrf')).json()
  const headers = { 'X-CSRF-Token': csrf_token }
  const questionResponse = await page.request.post('/api/staff/questions', {
    headers,
    data: {
      type: 'TRUE_FALSE',
      content: `阅卷入口 ${suffix}`,
      options: [],
      standard_answer: false,
      subject: '阅卷入口测试',
      knowledge_tags: [],
      difficulty: 'MEDIUM',
    },
  })
  expect(questionResponse.ok()).toBeTruthy()
  const question = await questionResponse.json()
  const paperResponse = await page.request.post('/api/staff/papers', {
    headers,
    data: {
      title: `阅卷入口试卷 ${suffix}`,
      questions: [{ question_id: question.id, score: '5.0' }],
    },
  })
  expect(paperResponse.ok()).toBeTruthy()
  const paper = await paperResponse.json()
  const examResponse = await page.request.post('/api/staff/exams', {
    headers,
    data: { title: `阅卷入口考试 ${suffix}`, source_paper_id: paper.id, audience_type: 'PUBLIC' },
  })
  expect(examResponse.ok()).toBeTruthy()
  const exam = await examResponse.json()
  const configured = await page.request.put(`/api/staff/exams/${exam.id}`, {
    headers,
    data: {
      ...exam,
      start_at: new Date(Date.now() - 60_000).toISOString(),
      end_at: new Date(Date.now() + 3_600_000).toISOString(),
      duration_seconds: 1800,
    },
  })
  expect(configured.ok()).toBeTruthy()
  const version = (await configured.json()).version
  const published = await page.request.post(`/api/staff/exams/${exam.id}/publish`, {
    headers,
    data: { version },
  })
  expect(published.ok()).toBeTruthy()
  return { id: exam.id, title: exam.title }
}

async function login(page: Page, name: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(name)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/home')
}

test.beforeEach(() => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
})

test('工作人员从主导航进入阅卷工作台并区分任务范围', async ({ page }) => {
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  await page
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '阅卷工作台', exact: true })
    .click()
  await expect(page.getByRole('heading', { name: '阅卷工作台', level: 1 })).toBeVisible()
  await expect(page.getByRole('button', { name: '我的任务', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '待指派', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '已完成', exact: true })).toBeVisible()
})

test('共享考试有独立答卷与最终成绩区域并明确最后有效提交口径', async ({ page }) => {
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const exam = await createPublishedExam(page)
  await page.goto(`/staff/exams/${exam.id}`)
  await page.getByRole('tab', { name: '答卷与成绩', exact: true }).click()
  await expect(page.getByRole('button', { name: '全部答卷', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '最终成绩', exact: true }).click()
  await expect(
    page.getByText('最终成绩取最后一次有效提交；该次待批改时不显示此前成绩。', { exact: true }),
  ).toBeVisible()
})

test('工作人员共享读取提交答卷与评分依据，管理员首阅保持只读', async ({ page, browser }) => {
  test.setTimeout(60_000)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const fixture = await gradingFixture(page, browser, 3)
  await waitForTask(page, fixture.exam.id, fixture.attemptId)
  await page.goto(`/staff/attempts/${fixture.attemptId}`)
  await expect(page.getByRole('heading', { name: fixture.exam.title, level: 1 })).toBeVisible()
  await expect(page.getByText('第一题学生论证', { exact: true })).toBeVisible()
  await expect(page.getByText('评分依据1', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '保存本题评分', exact: true })).toHaveCount(0)
  await expect(page.getByText(/仅指定教师可完成整卷首阅/)).toBeVisible()
})

test('已发布快照通过专门评分依据表单更正且必须填写原因', async ({ page }, testInfo) => {
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const exam = await createPublishedExam(page)
  await page.goto(`/staff/exams/${exam.id}`)
  await page.getByRole('tab', { name: '题目快照', exact: true }).click()
  await page.getByRole('button', { name: '更正第 1 题评分依据', exact: true }).click()
  await expect(page.getByRole('heading', { name: '更正评分依据', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '保存依据并重判', exact: true })).toBeDisabled()
  await expect(page.getByLabel('更正原因', { exact: true })).toBeVisible()
  await expect(page.getByLabel('判断标准答案', { exact: true })).toHaveValue('false')
  await page.getByLabel('判断标准答案', { exact: true }).selectOption('true')
  await page.getByLabel('更正原因', { exact: true }).fill('标准答案录入错误，修正为真。')
  await page.screenshot({
    path: testInfo.outputPath('standard-correction-desktop.png'),
    fullPage: true,
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({
    path: testInfo.outputPath('standard-correction-390.png'),
    fullPage: true,
  })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.getByRole('button', { name: '保存依据并重判', exact: true }).click()
  await expect(
    page.getByText('评分依据已更新，受影响的答卷将按当前依据重判。', { exact: true }),
  ).toBeVisible()
  const updated = await (await page.request.get(`/api/staff/exams/${exam.id}`)).json()
  expect(updated.questions[0].standard_answer).toBe(true)
})

test('指定教师整卷首阅完成后其他教师才可改分并必须记录原因', async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(60_000)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const fixture = await gradingFixture(page, browser, 4)
  await waitForTask(page, fixture.exam.id, fixture.attemptId)
  const firstContext = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.teachers[0]!.loginName,
    fixturePassword,
  )
  const otherContext = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.teachers[1]!.loginName,
    fixturePassword,
  )
  try {
    const first = await firstContext.newPage()
    const other = await otherContext.newPage()
    await first.goto('/staff/grading-tasks')
    await expect(first.getByRole('button', { name: '我的任务', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await first
      .getByRole('row')
      .filter({ hasText: fixture.exam.title })
      .getByRole('link', { name: '开始阅卷 →', exact: true })
      .click()
    await expect(first.getByLabel('评分分值', { exact: true })).toBeVisible()
    await first.getByLabel('评分分值', { exact: true }).fill('3.5')
    await first.getByLabel('阅卷评语', { exact: true }).fill('论证完整，关键概念还需补充。')
    await first.getByRole('button', { name: '保存本题评分', exact: true }).click()
    await expect(first.getByText('本题评分已保存。', { exact: true })).toBeVisible()
    await other.goto(`/staff/attempts/${fixture.attemptId}`)
    await expect(other.getByRole('button', { name: '保存本题评分', exact: true })).toHaveCount(0)
    await expect(other.getByText('整卷首阅尚未完成', { exact: true })).toBeVisible()
    await first.getByRole('button', { name: '查看第 2 题', exact: true }).click()
    await expect(first.getByText('第二题学生论证', { exact: true })).toBeVisible()
    await first.getByLabel('评分分值', { exact: true }).fill('4.0')
    await first.getByRole('button', { name: '保存本题评分', exact: true }).click()
    await expect(first.getByText('整卷首阅已完成', { exact: true })).toBeVisible()
    await expect(first.getByText('12.5 分', { exact: true })).toBeVisible()
    await other.reload()
    await other.getByLabel('评分分值', { exact: true }).fill('2.0')
    await expect(other.getByRole('button', { name: '保存本题评分', exact: true })).toBeDisabled()
    await other.getByLabel('改分原因', { exact: true }).fill('复核后未充分说明关键概念，调整分值。')
    await other.getByRole('button', { name: '保存本题评分', exact: true }).click()
    await expect(other.getByText('11.0 分', { exact: true })).toBeVisible()
    await other.evaluate(() => {
      if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
      window.scrollTo(0, 0)
    })
    await other.screenshot({
      path: testInfo.outputPath('grading-completed-desktop.png'),
      fullPage: true,
    })
    await other.setViewportSize({ width: 390, height: 844 })
    await other.evaluate(() => {
      if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
      window.scrollTo(0, 0)
    })
    await other.screenshot({
      path: testInfo.outputPath('grading-completed-390.png'),
      fullPage: true,
    })
    expect(await other.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      390,
    )
  } finally {
    await Promise.allSettled([firstContext.close(), otherContext.close()])
  }
})

test('并发改分保留当前输入并提示冲突，确认重读后显示最新评分', async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(60_000)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const fixture = await gradingFixture(page, browser, 3)
  await waitForTask(page, fixture.exam.id, fixture.attemptId)
  const firstContext = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.teachers[0]!.loginName,
    fixturePassword,
  )
  const otherContext = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.teachers[1]!.loginName,
    fixturePassword,
  )
  try {
    await gradeWholeAttempt(firstContext.request, fixture.attemptId)
    const first = await firstContext.newPage()
    const other = await otherContext.newPage()
    await first.goto(`/staff/attempts/${fixture.attemptId}`)
    await other.goto(`/staff/attempts/${fixture.attemptId}`)
    await expect(other.getByLabel('评分分值', { exact: true })).toHaveValue('4.0')
    await first.getByLabel('评分分值', { exact: true }).fill('3.0')
    await first.getByLabel('改分原因', { exact: true }).fill('教师复核，核心概念部分缺失。')
    await first.getByRole('button', { name: '保存本题评分', exact: true }).click()
    await expect(first.getByText('12.0 分', { exact: true })).toBeVisible()
    await other.getByLabel('评分分值', { exact: true }).fill('2.0')
    await other.getByLabel('改分原因', { exact: true }).fill('另一位教师的旧版本复核。')
    await other.getByRole('button', { name: '保存本题评分', exact: true }).click()
    await expect(
      other.getByText('评分已发生变化，当前输入已保留。请重新读取最新评分后再保存。', {
        exact: true,
      }),
    ).toBeVisible()
    await expect(other.getByLabel('评分分值', { exact: true })).toHaveValue('2.0')
    await expect(other.getByRole('button', { name: '保存本题评分', exact: true })).toBeDisabled()
    await other.screenshot({
      path: testInfo.outputPath('grading-version-conflict.png'),
      fullPage: true,
    })
    await other.getByRole('button', { name: '重新读取最新评分', exact: true }).click()
    await other.getByRole('button', { name: '放弃输入并重新读取', exact: true }).click()
    await expect(other.getByLabel('评分分值', { exact: true })).toHaveValue('3.0')
    await expect(other.getByLabel('改分原因', { exact: true })).toBeEmpty()
  } finally {
    await Promise.allSettled([firstContext.close(), otherContext.close()])
  }
})

test('共享评分历史展示评分人、前后分值与更正原因', async ({ page, browser }, testInfo) => {
  test.setTimeout(60_000)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const fixture = await gradingFixture(page, browser, 3)
  await waitForTask(page, fixture.exam.id, fixture.attemptId)
  const firstContext = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.teachers[0]!.loginName,
    fixturePassword,
  )
  try {
    const detail = await gradeWholeAttempt(firstContext.request, fixture.attemptId)
    const question = detail.questions[0]
    await apiWrite(firstContext.request, `/staff/answers/${question.answer.id}/grade`, {
      version: question.answer.version,
      grading_revision: question.grading_revision,
      score: '2.5',
      comment: '补充针对性评语。',
      reason: '复核论证质量，修正人工评分。',
    })
    await page.goto(`/staff/attempts/${fixture.attemptId}`)
    await expect(page.getByRole('button', { name: '查看本题评分历史', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '查看本题评分历史', exact: true }).click()
    const history = page.getByRole('dialog')
    await expect(history.getByText('4.0 → 2.5 分', { exact: true })).toBeVisible()
    await expect(history.getByText('复核论证质量，修正人工评分。', { exact: true })).toBeVisible()
    await expect(history.getByText('首阅测试教师', { exact: true }).first()).toBeVisible()
    await expect(history.getByText('补充针对性评语。', { exact: true })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath('grading-history.png'), fullPage: true })
  } finally {
    await firstContext.close()
  }
})

test('指定教师停用后管理员改派必须说明原因并保留已评题分', async ({ page, browser }, testInfo) => {
  test.setTimeout(60_000)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const fixture = await gradingFixture(page, browser, 3)
  await waitForTask(page, fixture.exam.id, fixture.attemptId)
  const firstContext = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.teachers[0]!.loginName,
    fixturePassword,
  )
  try {
    const detail = await (
      await firstContext.request.get(`/api/staff/attempts/${fixture.attemptId}`)
    ).json()
    const question = detail.questions[0]
    await apiWrite(firstContext.request, `/staff/answers/${question.answer.id}/grade`, {
      version: question.answer.version,
      grading_revision: question.grading_revision,
      score: '3.5',
      comment: '已有首题评分应保留。',
      reason: null,
    })
    await apiWrite(
      page.request,
      `/admin/users/${fixture.teachers[0]!.id}`,
      {
        login_name: fixture.teachers[0]!.loginName,
        real_name: '首阅测试教师',
        status: 'DEACTIVATED',
      },
      'PATCH',
    )
    await page.goto(`/staff/attempts/${fixture.attemptId}`)
    await expect(page.getByText('待指派', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '改派阅卷任务', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '改派阅卷任务', exact: true }).click()
    const modal = page.getByRole('dialog')
    await modal.getByLabel('搜索阅卷教师', { exact: true }).fill(fixture.teachers[1]!.loginName)
    await modal.getByRole('button', { name: '查询阅卷教师', exact: true }).click()
    await modal.getByLabel('选择阅卷教师', { exact: true }).selectOption(fixture.teachers[1]!.id)
    await expect(modal.getByRole('button', { name: '确认改派', exact: true })).toBeDisabled()
    await modal
      .getByLabel('改派原因', { exact: true })
      .fill('原阅卷教师停用，交由另一位激活教师继续整卷首阅。')
    await page.screenshot({ path: testInfo.outputPath('grading-reassignment.png'), fullPage: true })
    await modal.getByRole('button', { name: '确认改派', exact: true }).click()
    await expect(
      page.getByText('阅卷任务已改派，已有题分和评分历史已保留。', { exact: true }),
    ).toBeVisible()
    await expect(page.getByText('共享改分教师', { exact: true })).toBeVisible()
    await expect(page.getByText('已有首题评分应保留。', { exact: true })).toBeVisible()
    const latest = await (await page.request.get(`/api/staff/attempts/${fixture.attemptId}`)).json()
    expect(latest.questions[0].answer.score).toBe('3.5')
    expect(latest.task.assigned_teacher.id).toBe(fixture.teachers[1]!.id)
  } finally {
    await firstContext.close()
  }
})

test('最终成绩等待最后有效提交判完再取低分，学生已批改收据仍隐藏成绩', async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(60_000)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const fixture = await gradingFixture(page, browser, 7)
  const studentContext = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.student.loginName,
    fixturePassword,
  )
  const teacherContext = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.teachers[0]!.loginName,
    fixturePassword,
  )
  try {
    const last = await submitAttempt(studentContext.request, fixture.exam.id, [
      '最后一次简答一',
      '最后一次简答二',
      false,
    ])
    await waitForTask(page, fixture.exam.id, fixture.attemptId)
    await gradeWholeAttempt(teacherContext.request, fixture.attemptId)
    await page.goto(`/staff/exams/${fixture.exam.id}`)
    await page.getByRole('tab', { name: '答卷与成绩', exact: true }).click()
    await page.getByRole('button', { name: '最终成绩', exact: true }).click()
    await page.getByLabel('搜索成绩学生', { exact: true }).fill(fixture.student.loginName)
    await page.getByRole('button', { name: '查询最终成绩', exact: true }).click()
    const row = page.getByRole('row').filter({ hasText: fixture.student.loginName })
    await expect(row.getByText('第 2 次作答', { exact: true })).toBeVisible()
    await expect(row.getByText('待批改', { exact: true })).toBeVisible()
    await expect(row).not.toContainText('13.0 分')
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: testInfo.outputPath('final-result-pending.png'), fullPage: true })
    await gradeWholeAttempt(teacherContext.request, last.id, ['1.0', '2.0'])
    await page.getByRole('button', { name: '查询最终成绩', exact: true }).click()
    await expect(row.getByText('8.0 分', { exact: true })).toBeVisible()
    const student = await studentContext.newPage()
    await student.goto(`/student/attempts/${last.id}`)
    await expect(
      student.getByText('本次答卷已完成批改，成绩将在整场结果公布后开放。', { exact: true }),
    ).toBeVisible()
    await expect(student.getByRole('navigation', { name: '题目导航' })).toHaveCount(0)
    await expect(student.getByText('8.0 分', { exact: true })).toHaveCount(0)
    const receipt = await (await student.request.get(`/api/student/attempts/${last.id}`)).json()
    expect(receipt.grading_status).toBe('GRADED')
    expect(receipt.questions).toEqual([])
    expect(receipt).not.toHaveProperty('final_score')
    await page.screenshot({
      path: testInfo.outputPath('final-result-completed-desktop.png'),
      fullPage: true,
    })
    await page.setViewportSize({ width: 390, height: 844 })
    await page.screenshot({
      path: testInfo.outputPath('final-result-completed-390.png'),
      fullPage: true,
    })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  } finally {
    await Promise.allSettled([studentContext.close(), teacherContext.close()])
  }
})

test('简答依据更正重开已完成任务且保留首阅事实，其他教师可重判', async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(60_000)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const fixture = await gradingFixture(page, browser, 3)
  await waitForTask(page, fixture.exam.id, fixture.attemptId)
  const firstContext = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.teachers[0]!.loginName,
    fixturePassword,
  )
  const otherContext = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.teachers[1]!.loginName,
    fixturePassword,
  )
  try {
    const before = await gradeWholeAttempt(firstContext.request, fixture.attemptId)
    await page.goto(`/staff/exams/${fixture.exam.id}`)
    await page.getByRole('tab', { name: '题目快照', exact: true }).click()
    await page.getByRole('button', { name: '更正第 1 题评分依据', exact: true }).click()
    await page
      .getByLabel('简答评分依据', { exact: true })
      .fill('新评分依据：应同时说明概念与推理过程。')
    await page
      .getByLabel('更正原因', { exact: true })
      .fill('补全简答评分依据，对已提交答卷重新审核。')
    await page.getByRole('button', { name: '保存依据并重判', exact: true }).click()
    await expect(
      page.getByText('评分依据已更新，受影响的答卷将按当前依据重判。', { exact: true }),
    ).toBeVisible()
    const pending = await (
      await page.request.get(`/api/staff/attempts/${fixture.attemptId}`)
    ).json()
    expect(pending.final_score).toBeNull()
    expect(pending.questions[0].answer.grading_status).toBe('PENDING')
    expect(pending.task.first_review_completed_at).toBe(before.task.first_review_completed_at)
    const other = await otherContext.newPage()
    await other.goto(`/staff/attempts/${fixture.attemptId}`)
    await expect(
      other.getByText('新评分依据：应同时说明概念与推理过程。', { exact: true }),
    ).toBeVisible()
    await expect(other.getByText('旧依据评分（待重判）', { exact: true })).toBeVisible()
    await expect(other.getByText('整卷首阅已完成', { exact: true })).toBeVisible()
    await other.evaluate(() => {
      if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
      window.scrollTo(0, 0)
    })
    await other.screenshot({
      path: testInfo.outputPath('short-answer-regrading.png'),
      fullPage: true,
    })
    await other.getByLabel('评分分值', { exact: true }).fill('2.5')
    await other.getByLabel('改分原因', { exact: true }).fill('根据补全的评分依据完成重新审核。')
    await other.getByRole('button', { name: '保存本题评分', exact: true }).click()
    await expect(other.getByText('11.5 分', { exact: true })).toBeVisible()
  } finally {
    await Promise.allSettled([firstContext.close(), otherContext.close()])
  }
})

test('纯客观答卷无需人工首阅，管理员任务默认显示待指派', async ({ page, browser }, testInfo) => {
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const exam = await createPublishedExam(page)
  const loginName = `I4A${Date.now()}${Math.floor(Math.random() * 1000)}`
  await apiWrite(page.request, '/auth/register', {
    student_no: loginName,
    real_name: '自动判分测试学生',
    email: `${loginName}@example.com`,
    phone_number: '13900000000',
    password: fixturePassword,
  })
  const reviews = await (await page.request.get(`/api/staff/reviews?q=${loginName}`)).json()
  await apiWrite(page.request, `/staff/reviews/${reviews.items[0].id}/decision`, {
    decision: 'APPROVED',
  })
  const studentContext = await signedContext(
    browser,
    new URL(page.url()).origin,
    loginName,
    fixturePassword,
  )
  try {
    const submitted = await submitAttempt(studentContext.request, exam.id, [false])
    await apiWrite(page.request, `/staff/exams/${exam.id}/grading/refresh`, {})
    await page.goto(`/staff/attempts/${submitted.id}`)
    await expect(page.getByText('5.0 分', { exact: true })).toBeVisible()
    await expect(page.getByText('无需人工阅卷', { exact: true })).toBeVisible()
    await expect(page.getByText('无需首阅', { exact: true })).toBeVisible()
    await expect(page.getByText(/仅指定教师可完成整卷首阅/)).toHaveCount(0)
    await page.evaluate(() => {
      if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
      window.scrollTo(0, 0)
    })
    await page.screenshot({
      path: testInfo.outputPath('automatic-grading-no-review.png'),
      fullPage: true,
    })
    await page.goto('/staff/grading-tasks')
    await expect(page.getByRole('button', { name: '待指派', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await page.screenshot({ path: testInfo.outputPath('admin-tasks-default.png'), fullPage: true })
  } finally {
    await studentContext.close()
  }
})
