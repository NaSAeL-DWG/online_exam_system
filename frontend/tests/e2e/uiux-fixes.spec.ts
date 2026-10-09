import { expect, test, type Page } from '@playwright/test'
import {
  apiWrite,
  fixturePassword,
  gradingFixture,
  signedContext,
  waitForTask,
} from './grading-fixtures'
import { publishFixture, resultsFixture } from './results-fixtures'

// 审核证据不保存含登录凭据的 trace；失败信息与截图留在私有输出目录。
test.use({ trace: 'off' })

async function createDraft(page: Page): Promise<string> {
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
  await page.getByLabel('密码').fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/home')
  const { csrf_token } = await (await page.request.get('/api/auth/csrf')).json()
  const headers = { 'X-CSRF-Token': csrf_token }
  const suffix = Date.now()
  const questionResponse = await page.request.post('/api/staff/questions', {
    headers,
    data: {
      type: 'TRUE_FALSE',
      content: `离开保护题目 ${suffix}`,
      options: [],
      standard_answer: false,
      explanation: null,
      subject: '数学',
      knowledge_tags: [],
      difficulty: 'MEDIUM',
    },
  })
  expect(questionResponse.ok()).toBeTruthy()
  const question = await questionResponse.json()
  const paperResponse = await page.request.post('/api/staff/papers', {
    headers,
    data: {
      title: `离开保护试卷 ${suffix}`,
      questions: [{ question_id: question.id, score: '5' }],
    },
  })
  expect(paperResponse.ok()).toBeTruthy()
  const paper = await paperResponse.json()
  const examResponse = await page.request.post('/api/staff/exams', {
    headers,
    data: { title: `离开保护考试 ${suffix}`, source_paper_id: paper.id, audience_type: 'PUBLIC' },
  })
  expect(examResponse.ok()).toBeTruthy()
  const exam = await examResponse.json()
  return `/staff/exams/${exam.id}`
}

test('未保存考试草稿离开前可保留编辑，确认放弃才丢弃，保存后正常返回', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  const path = await createDraft(page)
  await page.goto(path)
  await page.getByLabel('考试说明', { exact: true }).fill('尚未保存的考试说明')
  await page.getByRole('button', { name: '返回考试列表' }).click()
  await expect(page.getByText('放弃未保存修改？', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '继续编辑', exact: true }).click()
  await expect(page).toHaveURL(path)
  await expect(page.getByLabel('考试说明', { exact: true })).toHaveValue('尚未保存的考试说明')
  await page.getByRole('button', { name: '返回考试列表' }).click()
  await page.getByRole('button', { name: '放弃修改并离开', exact: true }).click()
  await expect(page).toHaveURL('/staff/exams')
  await page.goto(path)
  await expect(page.getByLabel('考试说明', { exact: true })).toHaveValue('')
  await page.getByLabel('考试说明', { exact: true }).fill('保存后的考试说明')
  await page.getByRole('button', { name: '保存考试草稿' }).click()
  await expect(page.getByText('考试草稿已保存', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '返回考试列表' }).click()
  await expect(page).toHaveURL('/staff/exams')
  await expect(page.getByText('放弃未保存修改？', { exact: true })).toBeHidden()
})

test('题目编辑器关闭前确认未保存修改，取消关闭后仍能保存', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await createDraft(page)
  await page.goto('/staff/questions')
  await page.getByRole('button', { name: '新建题目' }).click()
  await page.getByLabel('科目', { exact: true }).fill('离开保护')
  const content = `尚未保存的题干 ${Date.now()}`
  await page.getByLabel('题干', { exact: true }).fill(content)
  await page.getByRole('dialog').getByRole('button', { name: 'close', exact: true }).click()
  await expect(page.getByText('放弃未保存修改？', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '继续编辑', exact: true }).click()
  await expect(page.getByLabel('题干', { exact: true })).toHaveValue(content)
  await page.getByRole('button', { name: '保存题目', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByLabel('搜索题目').fill(content)
  await page.getByRole('button', { name: '查询题目' }).click()
  await expect(page.getByRole('row').filter({ hasText: content })).toBeVisible()
})

test('试卷编辑器按 Esc 时保留未保存输入，明确放弃后才关闭', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await createDraft(page)
  await page.goto('/staff/papers')
  await page.getByRole('button', { name: '新建试卷' }).click()
  await page.getByLabel('试卷名称', { exact: true }).fill('未保存的组卷工作')
  await page.keyboard.press('Escape')
  await expect(page.getByText('放弃未保存修改？', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '继续编辑', exact: true }).click()
  await expect(page.getByLabel('试卷名称', { exact: true })).toHaveValue('未保存的组卷工作')
  await expect(page.getByText('放弃未保存修改？', { exact: true })).toBeHidden()
  await page.getByRole('dialog').getByRole('button', { name: 'close', exact: true }).click()
  await page.getByRole('button', { name: '放弃修改并离开', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: '新建试卷' }).click()
  await expect(page.getByLabel('试卷名称', { exact: true })).toHaveValue('')
})

test('阅卷表单返回考试前确认未保存评分并可继续评分', async ({ page, browser }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await createDraft(page)
  const fixture = await gradingFixture(page, browser, 5)
  await waitForTask(page, fixture.exam.id, fixture.attemptId)
  const context = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.teachers[0]!.loginName,
    fixturePassword,
  )
  try {
    const teacher = await context.newPage()
    await teacher.goto(`/staff/attempts/${fixture.attemptId}`)
    await teacher.getByLabel('评分分值', { exact: true }).fill('3.5')
    await teacher.getByLabel('阅卷评语', { exact: true }).fill('尚未保存的评分说明')
    await teacher.getByRole('link', { name: '← 返回考试管理' }).click()
    await expect(teacher.getByText('放弃未保存修改？', { exact: true })).toBeVisible()
    await teacher.getByRole('button', { name: '继续编辑', exact: true }).click()
    await expect(teacher.getByLabel('评分分值', { exact: true })).toHaveValue('3.5')
    await expect(teacher.getByLabel('阅卷评语', { exact: true })).toHaveValue('尚未保存的评分说明')
    await teacher.getByRole('button', { name: '保存本题评分' }).click()
    await expect(teacher.getByText('评分已保存', { exact: false })).toBeVisible()
    await teacher.getByRole('link', { name: '← 返回考试管理' }).click()
    await expect(teacher).toHaveURL(`/staff/exams/${fixture.exam.id}`)
  } finally {
    await context.close()
  }
})

test('错题自动重读保留未保存备注，主动刷新和离开需确认，撤回后隐藏草稿', async ({
  page,
  browser,
}) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await createDraft(page)
  const fixture = await resultsFixture(page, browser)
  await publishFixture(page, fixture)
  try {
    const student = await fixture.context.newPage()
    const mistakes = await (await fixture.context.request.get('/api/student/mistakes')).json()
    const answerId = mistakes.items[0].answer_id
    await student.goto(`/student/mistakes/${answerId}`)
    await student.getByLabel('学习备注').fill('尚未保存但不能因窗口切换而丢失的备注')
    const refresh = student.waitForResponse((response) =>
      response.url().endsWith(`/api/student/mistakes/${answerId}`),
    )
    await student.evaluate(() => window.dispatchEvent(new Event('focus')))
    await (await refresh).finished()
    await expect(student.getByLabel('学习备注')).toHaveValue('尚未保存但不能因窗口切换而丢失的备注')
    await student.getByRole('button', { name: '刷新错题' }).click()
    await expect(student.getByText('放弃未保存修改？', { exact: true })).toBeVisible()
    await student.getByRole('button', { name: '继续编辑', exact: true }).click()
    await student.getByRole('link', { name: '← 返回我的错题' }).click()
    await expect(student.getByText('放弃未保存修改？', { exact: true })).toBeVisible()
    await student.getByRole('button', { name: '继续编辑', exact: true }).click()
    await student.getByRole('button', { name: '保存学习标记' }).click()
    await expect(student.getByText('学习标记已保存。', { exact: true })).toBeVisible()
    await student.getByLabel('学习备注').fill('结果撤回后不应留在页面上的备注')
    const exam = await (await page.request.get(`/api/staff/exams/${fixture.exam.id}`)).json()
    await apiWrite(page.request, `/staff/exams/${exam.id}/withdraw-results`, {
      version: exam.version,
      reason: '撤回后必须立即清理题目及草稿显示',
    })
    await student.evaluate(() => window.dispatchEvent(new Event('focus')))
    await expect(student.getByLabel('学习备注')).toHaveCount(0)
    await expect(student.getByText('暂无可查看的错题。')).toBeVisible()
    await student.getByRole('link', { name: '← 返回我的错题' }).click()
    await expect(student).toHaveURL('/student/mistakes')
  } finally {
    await fixture.context.close()
  }
})
