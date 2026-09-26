import { expect, test } from '@playwright/test'

test('同一试卷创建的考试快照独立于来源和彼此，可发布并撤回', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
  await page.getByLabel('密码').fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/home')
  const { csrf_token } = await (await page.request.get('/api/auth/csrf')).json()
  const headers = { 'X-CSRF-Token': csrf_token }
  const suffix = Date.now()
  const data = {
    type: 'TRUE_FALSE',
    content: `原题 ${suffix}`,
    options: [],
    standard_answer: false,
    explanation: null,
    subject: '数学',
    knowledge_tags: [],
    difficulty: 'MEDIUM',
  }
  const questionResponse = await page.request.post('/api/staff/questions', { headers, data })
  expect(questionResponse.ok()).toBeTruthy()
  const question = await questionResponse.json()
  const paperResponse = await page.request.post('/api/staff/papers', {
    headers,
    data: { title: `快照试卷 ${suffix}`, questions: [{ question_id: question.id, score: '2.5' }] },
  })
  expect(paperResponse.ok()).toBeTruthy()
  await page.getByText('考试管理', { exact: true }).click()
  const examUrls: string[] = []
  for (const index of [1, 2]) {
    await page.getByRole('button', { name: '创建考试' }).click()
    await page.getByLabel('考试名称', { exact: true }).fill(`快照考试 ${suffix}-${index}`)
    await page.getByLabel('搜索来源试卷').fill(String(suffix))
    await page.getByRole('button', { name: '查询来源试卷' }).click()
    await page.getByLabel('来源试卷', { exact: true }).selectOption({ label: `快照试卷 ${suffix}` })
    await page.getByRole('button', { name: '建立考试快照' }).click()
    await expect(page.getByRole('heading', { name: '考试草稿' })).toBeVisible()
    examUrls.push(page.url())
    await page.goto('/staff/exams')
  }
  expect(
    (
      await page.request.put(`/api/staff/questions/${question.id}`, {
        headers,
        data: { ...data, content: `来源已修改 ${suffix}`, version: question.version },
      })
    ).ok(),
  ).toBeTruthy()
  await page.goto(examUrls[0]!)
  await expect(page.getByTestId('exam-snapshot')).toContainText(`原题 ${suffix}`)
  await page.getByRole('button', { name: '编辑快照第 1 题' }).click()
  await page.getByLabel('题干', { exact: true }).fill(`独立快照 ${suffix}`)
  await page.getByRole('button', { name: '应用题目修改' }).click()
  await page.getByLabel('参考范围', { exact: true }).selectOption('PUBLIC')
  await page.getByLabel('开始时间（上海）').fill('2030-01-01T09:00')
  await page.getByLabel('结束时间（上海）').fill('2030-01-01T11:00')
  await page.getByLabel('作答时长（分钟）').fill('60')
  await page.getByLabel('题目乱序').check()
  await page.getByLabel('选项乱序').check()
  await page.getByRole('button', { name: '保存考试草稿' }).click()
  await expect(page.getByText('考试草稿已保存', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '发布考试', exact: true }).click()
  await page.getByRole('button', { name: '确认发布' }).click()
  await expect(page.getByText('已发布', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: '撤回考试发布' }).click()
  await page.getByRole('button', { name: '确认撤回' }).click()
  await expect(page.getByRole('heading', { name: '考试草稿' })).toBeVisible()
  await expect(page.getByTestId('exam-snapshot')).toContainText(`独立快照 ${suffix}`)
  await page.goto(examUrls[1]!)
  await expect(page.getByTestId('exam-snapshot')).toContainText(`原题 ${suffix}`)
  await expect(page.getByTestId('exam-snapshot')).not.toContainText(`独立快照 ${suffix}`)
  await page.screenshot({ path: 'test-results/visual/exam-draft.png', fullPage: true })
})
