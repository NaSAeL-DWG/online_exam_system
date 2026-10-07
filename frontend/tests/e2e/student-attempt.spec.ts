import { expect, test, type Page } from '@playwright/test'

const studentPassword = 'Student123!'

async function login(page: Page, name: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(name)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/home')
}

async function createStudent(page: Page): Promise<string> {
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const name = `I3S${suffix}`
  const { csrf_token } = await (await page.request.get('/api/auth/csrf')).json()
  const headers = { 'X-CSRF-Token': csrf_token }
  const registered = await page.request.post('/api/auth/register', {
    headers,
    data: {
      student_no: name,
      real_name: '限时作答测试学生',
      email: `${name}@example.com`,
      phone_number: '13900000000',
      password: studentPassword,
    },
  })
  expect(registered.ok()).toBeTruthy()
  const reviews = await (await page.request.get(`/api/staff/reviews?q=${name}`)).json()
  const approved = await page.request.post(`/api/staff/reviews/${reviews.items[0].id}/decision`, {
    headers,
    data: { decision: 'APPROVED' },
  })
  expect(approved.ok()).toBeTruthy()
  await page.getByRole('button', { name: '退出登录' }).click()
  return name
}

async function createExam(
  page: Page,
  durationSeconds = 1800,
  maxAttempts = 2,
): Promise<{ id: string; title: string }> {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const { csrf_token } = await (await page.request.get('/api/auth/csrf')).json()
  const headers = { 'X-CSRF-Token': csrf_token }
  const teacherResponse = await page.request.post('/api/admin/teachers', {
    headers,
    data: {
      teacher_no: `I3T${suffix}`,
      real_name: '作答测试阅卷教师',
      email: `i3t-${suffix}@example.com`,
      phone_number: '13800000000',
      temporary_password: 'Teacher123!',
    },
  })
  expect(teacherResponse.ok()).toBeTruthy()
  const { user: teacher } = await teacherResponse.json()
  const questions = []
  for (const type of ['SINGLE_CHOICE', 'MULTIPLE_CHOICE', 'TRUE_FALSE', 'SHORT_ANSWER']) {
    const options = type.includes('CHOICE')
      ? [
          { id: crypto.randomUUID(), content: '选项甲' },
          { id: crypto.randomUUID(), content: '选项乙' },
        ]
      : []
    const response = await page.request.post('/api/staff/questions', {
      headers,
      data: {
        type,
        content: `${type} ${suffix}`,
        options,
        standard_answer:
          type === 'TRUE_FALSE'
            ? false
            : type === 'SHORT_ANSWER'
              ? null
              : options.map((option) => option.id).slice(0, type === 'SINGLE_CHOICE' ? 1 : 2),
        subject: '作答测试',
        knowledge_tags: [],
        difficulty: 'MEDIUM',
      },
    })
    expect(response.ok()).toBeTruthy()
    questions.push(await response.json())
  }
  const paperResponse = await page.request.post('/api/staff/papers', {
    headers,
    data: {
      title: `作答试卷${suffix}`,
      questions: questions.map((question) => ({ question_id: question.id, score: '5.0' })),
    },
  })
  expect(paperResponse.ok()).toBeTruthy()
  const paper = await paperResponse.json()
  const created = await page.request.post('/api/staff/exams', {
    headers,
    data: {
      title: `作答考试${suffix}`,
      source_paper_id: paper.id,
      audience_type: 'PUBLIC',
      description: '请确认作答规则后主动开始。',
    },
  })
  expect(created.ok()).toBeTruthy()
  const exam = await created.json()
  const configured = await page.request.put(`/api/staff/exams/${exam.id}`, {
    headers,
    data: {
      ...exam,
      start_at: new Date(Date.now() - 60_000).toISOString(),
      end_at: new Date(Date.now() + 3_600_000).toISOString(),
      duration_seconds: durationSeconds,
      max_attempts: maxAttempts,
      grader_ids: [teacher.id],
    },
  })
  expect(configured.ok()).toBeTruthy()
  const configuredExam = await configured.json()
  const published = await page.request.post(`/api/staff/exams/${exam.id}/publish`, {
    headers,
    data: { version: configuredExam.version },
  })
  expect(published.ok()).toBeTruthy()
  return { id: exam.id, title: exam.title }
}

test.beforeEach(() => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
})

test('已激活学生可以从工作台进入自己的考试列表', async ({ page }) => {
  const name = await createStudent(page)
  await login(page, name, studentPassword)
  await page
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '我的考试', exact: true })
    .click()
  await expect(page.getByRole('heading', { name: '我的考试', level: 1 })).toBeVisible()
  await expect(page.getByText('仅点击开始作答才会使用一次考试机会。')).toBeVisible()
})

test('学生主动开始后保存四类答案，刷新恢复同次作答并等待简答保存后交卷', async ({
  page,
}, testInfo) => {
  test.setTimeout(60_000)
  const student = await createStudent(page)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const exam = await createExam(page)
  await page.getByRole('button', { name: '退出登录' }).click()
  await login(page, student, studentPassword)
  await page.goto(`/student/exams/${exam.id}`)
  await expect(page.getByRole('heading', { name: exam.title, level: 1 })).toBeVisible()
  await expect(page.getByText('已使用 0 / 2 次', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '开始作答', exact: true }).click()
  await expect(page.getByRole('navigation', { name: '题目导航' })).toBeVisible()
  const attemptUrl = page.url()
  await page.getByRole('radio', { name: 'A. 选项甲', exact: true }).check()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('已保存')
  await page.getByRole('button', { name: '第 2 题', exact: true }).click()
  await page.getByRole('checkbox', { name: 'A. 选项甲', exact: true }).check()
  await page.getByRole('checkbox', { name: 'B. 选项乙', exact: true }).check()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('已保存')
  await page.getByRole('button', { name: '第 3 题', exact: true }).click()
  await page.getByRole('radio', { name: '错误', exact: true }).check()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('已保存')
  await page.getByRole('button', { name: '☆ 标记待检查', exact: true }).click()
  const beforeRefresh = await (
    await page.request.get(new URL(attemptUrl).pathname.replace('/student/', '/api/student/'))
  ).json()
  await page.reload()
  await expect(page).toHaveURL(attemptUrl)
  await page.getByRole('button', { name: '第 3 题', exact: true }).click()
  await expect(page.getByRole('radio', { name: '错误', exact: true })).toBeChecked()
  const afterRefresh = await (
    await page.request.get(new URL(attemptUrl).pathname.replace('/student/', '/api/student/'))
  ).json()
  expect(afterRefresh.deadline_at).toBe(beforeRefresh.deadline_at)
  await expect(page.getByRole('button', { name: '★ 已标记待检查', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page.screenshot({ path: testInfo.outputPath('workspace-desktop.png'), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: testInfo.outputPath('workspace-390.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.getByRole('button', { name: '第 4 题', exact: true }).click()
  await page
    .getByRole('textbox', { name: '简答答案', exact: true })
    .fill('提交时还在防抖窗口中的答案。')
  await page.getByRole('button', { name: '提交答卷', exact: true }).click()
  const beforeSubmit = await (
    await page.request.get(new URL(attemptUrl).pathname.replace('/student/', '/api/student/'))
  ).json()
  expect(beforeSubmit.questions[2].answer.answer_data).toBe(false)
  expect(beforeSubmit.questions[3].answer.answer_data).toBe('提交时还在防抖窗口中的答案。')
  await page.getByRole('button', { name: '确认交卷', exact: true }).click()
  await expect(page.getByRole('heading', { name: '答卷已提交', level: 2 })).toBeVisible()
  const latest = await (
    await page.request.get(new URL(attemptUrl).pathname.replace('/student/', '/api/student/'))
  ).json()
  expect(latest.status).toBe('SUBMITTED')
  expect(latest.questions).toEqual([])
})

test('复制页面保持只读，主动接管读取服务器答案并隔离旧页面的在途保存', async ({
  page,
  context,
}) => {
  test.setTimeout(60_000)
  const student = await createStudent(page)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const exam = await createExam(page)
  await page.getByRole('button', { name: '退出登录' }).click()
  await login(page, student, studentPassword)
  await page.goto(`/student/exams/${exam.id}`)
  await page.getByRole('button', { name: '开始作答', exact: true }).click()
  await page.getByRole('radio', { name: 'A. 选项甲', exact: true }).check()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('已保存')
  let finishResponse: () => void = () => {}
  const responseGate = new Promise<void>((resolve) => {
    finishResponse = resolve
  })
  let confirmServerSave: () => void = () => {}
  const serverSaved = new Promise<void>((resolve) => {
    confirmServerSave = resolve
  })
  await page.route(
    '**/api/student/attempts/*/answers/*',
    async (route) => {
      const response = await route.fetch()
      confirmServerSave()
      await responseGate
      await route.fulfill({ response })
    },
    { times: 1 },
  )
  await page.getByRole('radio', { name: 'B. 选项乙', exact: true }).check()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('保存中…')
  await serverSaved
  const copiedPagePromise = context.waitForEvent('page')
  // window.open 按浏览器规则复制 opener 的 sessionStorage，模拟用户复制已有标签页。
  await page.evaluate((url) => window.open(url, '_blank'), page.url())
  const copied = await copiedPagePromise
  await expect(copied.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeDisabled()
  await copied.getByRole('button', { name: '主动接管此答卷', exact: true }).click()
  await expect(copied.getByRole('radio', { name: 'B. 选项乙', exact: true })).toBeChecked()
  await expect(page.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeDisabled()
  await copied.getByRole('radio', { name: 'A. 选项甲', exact: true }).check()
  await expect(copied.getByRole('status', { name: '本题保存状态' })).toHaveText('已保存')
  finishResponse()
  await copied.reload()
  await expect(copied.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeChecked()
  await page.goto('/home')
  await page.goBack()
  await expect(page.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: '主动接管此答卷', exact: true }).click()
  await expect(page.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeChecked()
  await expect(copied.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeDisabled()
  const current = await (
    await page.request.get(new URL(page.url()).pathname.replace('/student/', '/api/student/'))
  ).json()
  expect(current.attempt_no).toBe(1)
})

test('教师取消整场考试必须说明原因并确认无法恢复', async ({ page }) => {
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const exam = await createExam(page)
  await page.goto(`/staff/exams/${exam.id}`)
  await page.getByRole('button', { name: '取消整场考试', exact: true }).click()
  await expect(
    page.getByText('取消后全部作答将废弃，考试无法恢复。', { exact: true }),
  ).toBeVisible()
  await page.getByLabel('取消考试原因', { exact: true }).fill('考试安排调整，另行组织考试。')
  await page.getByRole('button', { name: '确认取消整场考试', exact: true }).click()
  await expect(page.getByText('本场考试已取消，无法恢复。', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByText('考试安排调整，另行组织考试。', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '发布考试', exact: true })).toHaveCount(0)
})

test('保存响应丢失后的新草稿在刷新时核对服务器版本，断线恢复后可继续上传', async ({
  page,
  context,
}) => {
  test.setTimeout(60_000)
  const student = await createStudent(page)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const exam = await createExam(page)
  await page.getByRole('button', { name: '退出登录' }).click()
  await login(page, student, studentPassword)
  await page.goto(`/student/exams/${exam.id}`)
  await page.getByRole('button', { name: '开始作答', exact: true }).click()
  await expect(page.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeEnabled()
  let disconnected = true
  let firstDelivery = true
  await page.route('**/api/student/attempts/*/answers/*', async (route) => {
    if (!disconnected) {
      await route.continue()
      return
    }
    if (firstDelivery) {
      firstDelivery = false
      await route.fetch()
    }
    await route.abort('connectionreset')
  })
  await page.route(/\/api\/student\/attempts\/[^/]+$/, async (route) => {
    if (disconnected) await route.abort('connectionreset')
    else await route.continue()
  })
  await page.getByRole('radio', { name: 'A. 选项甲', exact: true }).check()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('保存失败')
  await page.getByRole('button', { name: '清空答案', exact: true }).click()
  disconnected = false
  await page.reload()
  await expect(page.getByRole('radio', { name: 'A. 选项甲', exact: true })).not.toBeChecked()
  await expect(page.getByRole('radio', { name: 'B. 选项乙', exact: true })).not.toBeChecked()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('已保存')
  await page.getByRole('button', { name: '第 4 题', exact: true }).click()
  await context.setOffline(true)
  await page
    .getByRole('textbox', { name: '简答答案', exact: true })
    .fill('恢复网络后仍在截止前保存的离线草稿。')
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('保存失败')
  await page.getByRole('button', { name: '提交答卷', exact: true }).click()
  await expect(
    page.getByText('仍有答案未保存成功。请先重试或处理版本冲突，再提交答卷。', { exact: true }),
  ).toBeVisible()
  await context.setOffline(false)
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('已保存')
  const current = await (
    await page.request.get(new URL(page.url()).pathname.replace('/student/', '/api/student/'))
  ).json()
  expect(current.questions[0].answer.answer_data).toBeNull()
  expect(current.questions[3].answer.answer_data).toBe('恢复网络后仍在截止前保存的离线草稿。')
})

test('到期自动交卷不被空题阻止，未上传草稿不能在截止后补传', async ({ page }, testInfo) => {
  test.setTimeout(60_000)
  const student = await createStudent(page)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const exam = await createExam(page, 8)
  await page.getByRole('button', { name: '退出登录' }).click()
  await login(page, student, studentPassword)
  await page.goto(`/student/exams/${exam.id}`)
  await page.getByRole('button', { name: '开始作答', exact: true }).click()
  let pendingUrl = ''
  let pendingBody: unknown = null
  await page.route('**/api/student/attempts/*/answers/*', async (route) => {
    pendingUrl = route.request().url()
    pendingBody = route.request().postDataJSON()
    await route.abort('connectionreset')
  })
  await page.getByRole('radio', { name: 'A. 选项甲', exact: true }).check()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('保存失败')
  await expect(page.getByRole('heading', { name: '答卷已提交', level: 2 })).toBeVisible({
    timeout: 20_000,
  })
  await expect(page.getByText('时间到，系统已自动交卷', { exact: true })).toBeVisible()
  await expect(page.getByText(/未上传的内容不计入答卷/)).toBeVisible()
  const { csrf_token } = await (await page.request.get('/api/auth/csrf')).json()
  const late = await page.request.put(pendingUrl, {
    headers: { 'X-CSRF-Token': csrf_token },
    data: pendingBody,
  })
  expect(late.status()).toBe(409)
  expect(['ATTEMPT_EXPIRED', 'ATTEMPT_SUBMITTED']).toContain((await late.json()).detail.code)
  await page.reload()
  await expect(page.getByText(/未上传的内容不计入答卷/)).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('timeout-receipt.png'), fullPage: true })
})

test('空题交卷明确列出题号，确认后只显示提交收据', async ({ page }) => {
  const student = await createStudent(page)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const exam = await createExam(page, 1800, 1)
  await page.getByRole('button', { name: '退出登录' }).click()
  await login(page, student, studentPassword)
  await page.goto(`/student/exams/${exam.id}`)
  await page.getByRole('button', { name: '开始作答', exact: true }).click()
  await page.getByRole('button', { name: '第 3 题', exact: true }).click()
  await page.getByRole('radio', { name: '错误', exact: true }).check()
  await page.getByRole('button', { name: '提交答卷', exact: true }).click()
  await expect(page.getByRole('dialog')).toContainText('第 1 题、第 2 题、第 4 题')
  await expect(page.getByRole('dialog')).not.toContainText('第 3 题')
  await page.getByRole('button', { name: '确认交卷', exact: true }).click()
  await expect(page.getByRole('heading', { name: '答卷已提交', level: 2 })).toBeVisible()
  await expect(page.getByRole('navigation', { name: '题目导航' })).toHaveCount(0)
  await page.getByRole('link', { name: '← 返回考试详情', exact: true }).click()
  await expect(page.getByText('本场考试的作答机会已用完。', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '查看提交状态', exact: true }).click()
  await expect(page.getByRole('heading', { name: '答卷已提交', level: 2 })).toBeVisible()
})

test('答案版本冲突保留本地内容，确认重读后显示服务器答案', async ({ page }, testInfo) => {
  const student = await createStudent(page)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const exam = await createExam(page)
  await page.getByRole('button', { name: '退出登录' }).click()
  await login(page, student, studentPassword)
  await page.goto(`/student/exams/${exam.id}`)
  await page.getByRole('button', { name: '开始作答', exact: true }).click()
  await expect(page.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeEnabled()
  const current = await (
    await page.request.get(new URL(page.url()).pathname.replace('/student/', '/api/student/'))
  ).json()
  await page.route(
    '**/api/student/attempts/*/answers/*',
    async (route) => {
      // 在公开 HTTP 边界写入另一版答案，再交付浏览器的旧版本请求。
      const body = route.request().postDataJSON()
      const changed = await route.fetch({
        postData: JSON.stringify({ ...body, answer_data: [current.questions[0].options[1].id] }),
      })
      expect(changed.ok()).toBeTruthy()
      await route.continue()
    },
    { times: 1 },
  )
  await page.getByRole('radio', { name: 'A. 选项甲', exact: true }).check()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('版本冲突')
  await expect(page.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeChecked()
  await page.screenshot({
    path: testInfo.outputPath('answer-version-conflict.png'),
    fullPage: true,
  })
  await page.getByRole('button', { name: '重新读取服务器答案', exact: true }).click()
  await expect(
    page.getByText('这会放弃本页尚未上传的修改。请先复制需要保留的简答内容。', { exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: '放弃本地修改并读取', exact: true }).click()
  await expect(page.getByRole('radio', { name: 'B. 选项乙', exact: true })).toBeChecked()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('已保存')
})

test('作答中资格撤销及整场取消立即阻止保存，并明确提示废弃状态', async ({ page, browser }) => {
  test.setTimeout(60_000)
  const student = await createStudent(page)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const exam = await createExam(page)
  const studentContext = await browser.newContext()
  const studentPage = await studentContext.newPage()
  try {
    await login(studentPage, student, studentPassword)
    await studentPage.goto(`/student/exams/${exam.id}`)
    await studentPage.getByRole('button', { name: '开始作答', exact: true }).click()
    await expect(studentPage.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeEnabled()
    const { csrf_token } = await (await page.request.get('/api/auth/csrf')).json()
    const headers = { 'X-CSRF-Token': csrf_token }
    const participants = await (
      await page.request.get(`/api/staff/exams/${exam.id}/participants?q=${student}`)
    ).json()
    const participant = participants.items[0]
    const cancelled = await page.request.post(
      `/api/staff/exams/${exam.id}/participants/${participant.id}/cancel`,
      { headers, data: { version: participant.version, reason: '核验参考资格。' } },
    )
    expect(cancelled.ok()).toBeTruthy()
    await studentPage.getByRole('radio', { name: 'A. 选项甲', exact: true }).check()
    await expect(
      studentPage.getByText('你的参考资格已撤销，相关作答已废弃，无法继续保存或交卷。').first(),
    ).toBeVisible()
    await expect(studentPage.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeDisabled()
    const changedParticipant = await cancelled.json()
    const restored = await page.request.post(
      `/api/staff/exams/${exam.id}/participants/${participant.id}/restore`,
      { headers, data: { version: changedParticipant.version, reason: '核验通过。' } },
    )
    expect(restored.ok()).toBeTruthy()
    await studentPage.goto(`/student/exams/${exam.id}`)
    await expect(studentPage.getByText('已使用 1 / 2 次', { exact: true })).toBeVisible()
    await studentPage.getByRole('button', { name: '开始作答', exact: true }).click()
    await expect(studentPage.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeEnabled()
    await page.goto(`/staff/exams/${exam.id}`)
    await page.getByRole('button', { name: '取消整场考试', exact: true }).click()
    await page.getByLabel('取消考试原因', { exact: true }).fill('整场安排取消。')
    await page.getByRole('button', { name: '确认取消整场考试', exact: true }).click()
    await expect(page.getByText('本场考试已取消，无法恢复。', { exact: true })).toBeVisible()
    await studentPage.getByRole('radio', { name: 'A. 选项甲', exact: true }).check()
    await expect(
      studentPage.getByText('本场考试已取消，相关作答已废弃，无法恢复。').first(),
    ).toBeVisible()
    await expect(studentPage.getByRole('button', { name: '提交答卷', exact: true })).toBeDisabled()
    await studentPage.goto(`/student/exams/${exam.id}`)
    await expect(studentPage.getByRole('alert')).toContainText(
      '本场考试已取消，相关作答已废弃，无法恢复。',
    )
    await expect(studentPage.getByRole('button', { name: '开始作答', exact: true })).toHaveCount(0)
  } finally {
    await studentContext.close()
  }
})

test('独立浏览器会话读取已有答卷保持只读，必须主动接管才能写入', async ({
  page,
  context,
  browser,
}) => {
  const student = await createStudent(page)
  await login(page, process.env.E2E_ADMIN_LOGIN!, process.env.E2E_ADMIN_PASSWORD!)
  const exam = await createExam(page)
  await page.getByRole('button', { name: '退出登录' }).click()
  await login(page, student, studentPassword)
  await page.goto(`/student/exams/${exam.id}`)
  await page.getByRole('button', { name: '开始作答', exact: true }).click()
  await page.getByRole('radio', { name: 'A. 选项甲', exact: true }).check()
  await expect(page.getByRole('status', { name: '本题保存状态' })).toHaveText('已保存')
  const attemptUrl = page.url()
  const apiUrl = new URL(attemptUrl).pathname.replace('/student/', '/api/student/')
  const before = await (await page.request.get(apiUrl)).json()
  // 独立浏览器会话复用登录 Cookie，但不会继承原页面的 sessionStorage 和 Web Lock。
  const otherContext = await browser.newContext({ storageState: await context.storageState() })
  const other = await otherContext.newPage()
  try {
    await other.goto(attemptUrl)
    await expect(other.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeDisabled()
    const readonly = await (await other.request.get(apiUrl)).json()
    expect(readonly.token_generation).toBe(before.token_generation)
    await other.getByRole('button', { name: '主动接管此答卷', exact: true }).click()
    await expect(other.getByRole('radio', { name: 'A. 选项甲', exact: true })).toBeChecked()
    await other.getByRole('radio', { name: 'B. 选项乙', exact: true }).check()
    await expect(other.getByRole('status', { name: '本题保存状态' })).toHaveText('已保存')
    if (await page.getByRole('radio', { name: 'B. 选项乙', exact: true }).isEnabled()) {
      await page.getByRole('radio', { name: 'B. 选项乙', exact: true }).check()
    }
    await expect(page.getByRole('radio', { name: 'B. 选项乙', exact: true })).toBeDisabled()
    await expect(page.getByText(/另一页面已接管此答卷/).first()).toBeVisible()
    const current = await (await other.request.get(apiUrl)).json()
    expect(current.questions[0].answer.answer_data).toEqual([current.questions[0].options[1].id])
  } finally {
    await otherContext.close()
  }
})
