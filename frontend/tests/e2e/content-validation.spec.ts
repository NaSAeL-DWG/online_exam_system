import { expect, test, type Page } from '@playwright/test'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import {
  apiWrite,
  fixturePassword,
  gradeWholeAttempt,
  gradingFixture,
  signedContext,
  waitForTask,
} from './grading-fixtures'

// 测试只读取私有凭据，不在日志、截图或浏览器 trace 中记录登录过程。
const privateEnvPath = path.resolve('..', '.local', 'e2e.env')
const privateEnv = existsSync(privateEnvPath) ? readFileSync(privateEnvPath, 'utf8') : ''
for (const line of privateEnv.split(/\r?\n/)) {
  const match = line.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/)
  if (match && !process.env[match[1]!])
    process.env[match[1]!] = match[2]!.replace(/^['"]|['"]$/g, '')
}
test.use({ trace: 'off', video: 'off' })
test.beforeEach(() => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
})

async function openAdmin(page: Page): Promise<void> {
  await page.goto('/login')
  await apiWrite(page.request, '/auth/login', {
    login_name: process.env.E2E_ADMIN_LOGIN,
    password: process.env.E2E_ADMIN_PASSWORD,
  })
}

async function contentFixture(page: Page) {
  const suffix = Date.now()
  const question = await apiWrite(page.request, '/staff/questions', {
    type: 'TRUE_FALSE',
    content: `内容校验题 ${suffix}`,
    options: [],
    standard_answer: false,
    subject: '内容校验',
    knowledge_tags: [],
    difficulty: 'MEDIUM',
  })
  const paper = await apiWrite(page.request, '/staff/papers', {
    title: `内容校验试卷 ${suffix}`,
    questions: [{ question_id: question.id, score: '5.0' }],
  })
  return { question, paper }
}

test('题目知识点超出数量时就近中文提示，纠正后可保存', async ({ page }) => {
  await openAdmin(page)
  await page.goto('/staff/questions')
  await page.getByRole('button', { name: '新建题目', exact: true }).click()
  await page.getByLabel('科目', { exact: true }).fill('内容校验')
  await page.getByLabel('题干', { exact: true }).fill(`知识点校验 ${Date.now()}`)
  await page
    .getByLabel('知识点标签')
    .fill(Array.from({ length: 31 }, (_, index) => `标签${index + 1}`).join('，'))
  const writes: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/api/staff/questions') && request.method() === 'POST')
      writes.push(request.url())
  })
  await page.getByRole('button', { name: '保存题目', exact: true }).click()
  const tags = page.getByLabel('知识点标签')
  await expect(tags).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByText('知识点最多填写 30 个。', { exact: true })).toBeVisible()
  await expect(tags).toBeFocused()
  expect(writes).toHaveLength(0)
  await tags.fill(Array.from({ length: 30 }, (_, index) => `标签${index + 1}`).join('，'))
  await page.getByRole('button', { name: '保存题目', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
})

test('题目空白字段与多选答案在本地校验，正确填写后放行', async ({ page }) => {
  await openAdmin(page)
  await page.goto('/staff/questions')
  await page.getByRole('button', { name: '新建题目', exact: true }).click()
  await page.getByLabel('题型', { exact: true }).selectOption('MULTIPLE_CHOICE')
  await page.getByLabel('科目', { exact: true }).fill('   ')
  await page.getByLabel('题干', { exact: true }).fill(`多选校验 ${Date.now()}`)
  await page.getByLabel('选项 1', { exact: true }).fill('   ')
  await page.getByLabel('选项 2', { exact: true }).fill('第二个选项')
  await page.getByLabel('正确选项 1', { exact: true }).check()
  await page.getByLabel('正确选项 2', { exact: true }).check()
  await page.getByRole('button', { name: '保存题目', exact: true }).click()
  await expect(page.getByLabel('科目', { exact: true })).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByLabel('科目', { exact: true })).toBeFocused()
  await expect(page.getByText('请填写科目。', { exact: true })).toBeVisible()
  await page.getByLabel('科目', { exact: true }).fill('数学')
  await page.getByRole('button', { name: '保存题目', exact: true }).click()
  await expect(page.getByLabel('选项 1', { exact: true })).toBeFocused()
  await expect(page.getByText('请填写选项内容。', { exact: true })).toBeVisible()
  await page.getByLabel('选项 1', { exact: true }).fill('第一个选项')
  await page.getByLabel('正确选项 2', { exact: true }).uncheck()
  await page.getByRole('button', { name: '保存题目', exact: true }).click()
  await expect(page.getByLabel('正确选项 1', { exact: true })).toBeFocused()
  await expect(page.getByText('多选题请至少选择两个正确选项。', { exact: true })).toBeVisible()
  await page.getByLabel('正确选项 2', { exact: true }).check()
  await page.getByRole('button', { name: '保存题目', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
})

test('阅卷小数与超分显示中文错误，零分与合法长评语可保存', async ({ page, browser }) => {
  test.setTimeout(60_000)
  await openAdmin(page)
  const fixture = await gradingFixture(page, browser, 3)
  await waitForTask(page, fixture.exam.id, fixture.attemptId)
  const graderContext = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.teachers[0]!.loginName,
    fixturePassword,
  )
  const grader = await graderContext.newPage()
  try {
    await grader.goto(`/staff/attempts/${fixture.attemptId}`)
    const score = grader.getByLabel('评分分值', { exact: true })
    const writes: string[] = []
    grader.on('request', (request) => {
      if (request.url().endsWith('/grade') && request.method() === 'POST')
        writes.push(request.url())
    })
    await score.fill('1.25')
    await grader.getByRole('button', { name: '保存本题评分', exact: true }).click()
    await expect(grader.getByText('评分分值最多保留 1 位小数。', { exact: true })).toBeVisible()
    await expect(score).toHaveAttribute('aria-invalid', 'true')
    await expect(score).toBeFocused()
    await score.fill('5.1')
    await grader.getByRole('button', { name: '保存本题评分', exact: true }).click()
    await expect(grader.getByText('评分分值不能超过 5.0 分。', { exact: true })).toBeVisible()
    expect(writes).toHaveLength(0)
    await score.fill('0')
    const longComment = '评'.repeat(2001)
    await grader.getByLabel('阅卷评语').fill(longComment)
    await expect(grader.getByLabel('阅卷评语')).toHaveValue(longComment)
    await grader.getByRole('button', { name: '保存本题评分', exact: true }).click()
    await expect(grader.getByText('本题评分已保存。', { exact: true })).toBeVisible()
    await expect(score).toHaveValue('0.0')
    await grader.getByLabel('改分原因', { exact: true }).fill('   ')
    await grader.getByRole('button', { name: '保存本题评分', exact: true }).click()
    await expect(grader.getByText('请填写改分原因。', { exact: true })).toBeVisible()
    await expect(grader.getByLabel('改分原因', { exact: true })).toBeFocused()
  } finally {
    await graderContext.close()
  }
})

test('试卷名称和题分提供中文校验，合法一位小数可保存', async ({ page }) => {
  await openAdmin(page)
  const { paper } = await contentFixture(page)
  await page.goto('/staff/papers')
  await page.getByLabel('搜索试卷').fill(paper.title)
  await page.getByRole('button', { name: '查询试卷', exact: true }).click()
  await page
    .getByRole('row')
    .filter({ hasText: paper.title })
    .getByRole('button', { name: '编辑', exact: true })
    .click()
  const writes: string[] = []
  page.on('request', (request) => {
    if (request.url().endsWith(`/staff/papers/${paper.id}`) && request.method() === 'PUT')
      writes.push(request.url())
  })
  await page.getByLabel('试卷名称').fill('   ')
  await page.getByLabel('第 1 题分值').fill('1.25')
  await page.getByRole('button', { name: '保存试卷', exact: true }).click()
  await expect(page.getByText('请填写试卷名称。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('试卷名称')).toBeFocused()
  await page.getByLabel('试卷名称').fill('卷'.repeat(200))
  await page.getByRole('button', { name: '保存试卷', exact: true }).click()
  await expect(page.getByText('题目分值最多保留 1 位小数。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('第 1 题分值')).toBeFocused()
  await page.getByLabel('第 1 题分值').fill('0')
  await page.getByRole('button', { name: '保存试卷', exact: true }).click()
  await expect(page.getByText('题目分值不能小于 0.1。', { exact: true })).toBeVisible()
  expect(writes).toHaveLength(0)
  await page.getByLabel('第 1 题分值').fill('2.5')
  await page.getByRole('button', { name: '保存试卷', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
  const saved = await (await page.request.get(`/api/staff/papers/${paper.id}`)).json()
  expect(saved.questions[0].score).toBe('2.5')
  expect(saved.title).toBe('卷'.repeat(200))
})

test('考试草稿跨分区定位数值错误，空时间和合法半分钟可保存', async ({ page }) => {
  await openAdmin(page)
  const { paper } = await contentFixture(page)
  const exam = await apiWrite(page.request, '/staff/exams', {
    title: `草稿校验 ${Date.now()}`,
    source_paper_id: paper.id,
    audience_type: 'PUBLIC',
  })
  await page.goto(`/staff/exams/${exam.id}`)
  await page.getByLabel('最多作答次数').fill('101')
  await page.getByRole('tab', { name: '题目快照', exact: true }).click()
  await page.getByRole('button', { name: '保存考试草稿', exact: true }).click()
  await expect(page.getByRole('tab', { name: '考试设置', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(page.getByText('最多作答次数不能超过 100。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('最多作答次数')).toBeFocused()
  await page.getByLabel('最多作答次数').fill('100')
  await page.getByLabel('作答时长（分钟）').fill('10081')
  await page.getByRole('button', { name: '保存考试草稿', exact: true }).click()
  await expect(page.getByText('作答时长不能超过 10080 分钟。', { exact: true })).toBeVisible()
  await page.getByLabel('作答时长（分钟）').fill('0.5')
  await page.getByLabel('及格百分比').fill('60.125')
  await page.getByRole('button', { name: '保存考试草稿', exact: true }).click()
  await expect(page.getByText('及格百分比最多保留 2 位小数。', { exact: true })).toBeVisible()
  await page.getByLabel('及格百分比').fill('60.25')
  await page.getByRole('button', { name: '保存考试草稿', exact: true }).click()
  await expect(page.getByText('考试草稿已保存', { exact: true })).toBeVisible()
  const saved = await (await page.request.get(`/api/staff/exams/${exam.id}`)).json()
  expect(saved.start_at).toBeNull()
  expect(saved.end_at).toBeNull()
  expect(saved.duration_seconds).toBe(30)
  expect(saved.max_attempts).toBe(100)
  expect(saved.pass_percentage).toBe('60.25')
  await page.getByRole('tab', { name: '题目快照', exact: true }).click()
  await page.getByLabel('快照第 1 题分值').fill('1.25')
  await page.getByRole('tab', { name: '考试设置', exact: true }).click()
  await page.getByRole('button', { name: '保存考试草稿', exact: true }).click()
  await expect(page.getByRole('tab', { name: '题目快照', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(page.getByText('题目分值最多保留 1 位小数。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('快照第 1 题分值')).toBeFocused()
  await page.getByLabel('快照第 1 题分值').fill('0.1')
  await page.getByRole('button', { name: '保存考试草稿', exact: true }).click()
  await expect(page.getByText('考试草稿已保存', { exact: true })).toBeVisible()
})

test('创建考试定位名称与来源，取消原因空白时就近说明', async ({ page }) => {
  await openAdmin(page)
  const { paper } = await contentFixture(page)
  await page.goto('/staff/exams')
  await page.getByRole('button', { name: '创建考试', exact: true }).click()
  await page.getByLabel('考试名称', { exact: true }).fill('   ')
  await page.getByRole('button', { name: '建立考试快照', exact: true }).click()
  await expect(page.getByText('请填写考试名称。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('考试名称', { exact: true })).toBeFocused()
  await page.getByLabel('考试名称', { exact: true }).fill(`创建校验 ${Date.now()}`)
  await page.getByRole('button', { name: '建立考试快照', exact: true }).click()
  await expect(page.getByText('请选择来源试卷。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('来源试卷', { exact: true })).toBeFocused()
  await page.getByLabel('来源试卷', { exact: true }).selectOption(paper.id)
  await page.getByRole('button', { name: '建立考试快照', exact: true }).click()
  await expect(page).toHaveURL(/\/staff\/exams\/[^/]+$/)
  await page.getByRole('button', { name: '取消整场考试', exact: true }).click()
  await page.getByLabel('取消考试原因', { exact: true }).fill('   ')
  await expect(page.getByRole('button', { name: '确认取消整场考试', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '确认取消整场考试', exact: true }).click()
  await expect(page.getByText('请填写取消考试原因。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('取消考试原因', { exact: true })).toBeFocused()
})

test('改派、评分依据更正和结果撤回表单就近说明必填原因', async ({ page, browser }) => {
  test.setTimeout(60_000)
  await openAdmin(page)
  const fixture = await gradingFixture(page, browser, 3)
  await waitForTask(page, fixture.exam.id, fixture.attemptId)
  await page.goto(`/staff/attempts/${fixture.attemptId}`)
  await page.getByRole('button', { name: '改派阅卷任务', exact: true }).click()
  await expect(page.getByRole('button', { name: '确认改派', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '确认改派', exact: true }).click()
  await expect(page.getByText('请选择阅卷教师。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('选择阅卷教师', { exact: true })).toBeFocused()
  await page.getByLabel('选择阅卷教师', { exact: true }).selectOption(fixture.teachers[0]!.id)
  await page.getByLabel('改派原因', { exact: true }).fill('   ')
  await page.getByRole('button', { name: '确认改派', exact: true }).click()
  await expect(page.getByText('请填写改派原因。', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '取消改派', exact: true }).click()
  await page.goto(`/staff/exams/${fixture.exam.id}`)
  await page.getByRole('tab', { name: '题目快照', exact: true }).click()
  await page.getByRole('button', { name: '更正第 1 题评分依据', exact: true }).click()
  await page.getByLabel('更正原因', { exact: true }).fill('   ')
  await expect(page.getByRole('button', { name: '保存依据并重判', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '保存依据并重判', exact: true }).click()
  await expect(page.getByText('请填写更正原因。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('更正原因', { exact: true })).toBeFocused()
  await page.getByRole('button', { name: '取消更正', exact: true }).click()
  const context = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.teachers[0]!.loginName,
    fixturePassword,
  )
  try {
    await gradeWholeAttempt(context.request, fixture.attemptId)
  } finally {
    await context.close()
  }
  const exam = await (await page.request.get(`/api/staff/exams/${fixture.exam.id}`)).json()
  await apiWrite(page.request, `/staff/exams/${fixture.exam.id}/publish-results`, {
    version: exam.version,
  })
  await page.reload()
  await page.getByRole('button', { name: '撤回已公布结果', exact: true }).click()
  await expect(page.getByRole('button', { name: '确认撤回结果', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '确认撤回结果', exact: true }).click()
  await expect(page.getByText('请填写撤回结果原因。', { exact: true })).toBeVisible()
  await expect(page.getByLabel('撤回结果原因', { exact: true })).toBeFocused()
})

test('题目导航朗读作答、保存失败和待检查状态，名字保持稳定', async ({ page, browser }) => {
  test.setTimeout(60_000)
  await openAdmin(page)
  const fixture = await gradingFixture(page, browser)
  await apiWrite(page.request, '/auth/logout', {})
  await apiWrite(page.request, '/auth/login', {
    login_name: fixture.student.loginName,
    password: fixturePassword,
  })
  const student = page
  await student.goto(`/student/exams/${fixture.exam.id}`)
  await student.getByRole('button', { name: '开始作答', exact: true }).click()
  const navigation = student.getByRole('navigation', { name: '题目导航', exact: true })
  const first = navigation.getByRole('button', { name: '第 1 题', exact: true })
  await expect(first).toHaveAccessibleDescription(/未作答.*已保存/)
  await student.route('**/api/student/attempts/*/answers/*', (route) =>
    route.request().method() === 'PUT' ? route.abort('failed') : route.continue(),
  )
  await student.getByLabel('简答答案', { exact: true }).fill('导航状态校验')
  await student.getByRole('button', { name: '☆ 标记待检查', exact: true }).click()
  await expect(first).toHaveAccessibleDescription(/已作答.*保存失败.*待检查/)
  await expect(first).toHaveAccessibleName('第 1 题')
  await expect(first).toHaveAttribute('aria-current', 'step')
  await student.unroute('**/api/student/attempts/*/answers/*')
  await student.getByRole('button', { name: '重试保存本题', exact: true }).click()
  await expect(first).toHaveAccessibleDescription(/已作答.*已保存.*待检查/)
  await navigation.getByRole('button', { name: '第 2 题', exact: true }).click()
  await expect(first).not.toHaveAttribute('aria-current', 'step')
  // 先离开主动轮询的作答页，结束页面租约后交给 Playwright 统一回收上下文。
  await student.goto(`/student/exams/${fixture.exam.id}`)
})
