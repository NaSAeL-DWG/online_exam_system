import { expect, test } from '@playwright/test'

test('组卷时教师可即时核对总分，调整顺序并保存后重新读取', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
  await page.getByLabel('密码').fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/home')
  const { csrf_token } = await (await page.request.get('/api/auth/csrf')).json()
  const suffix = Date.now()
  for (const index of [1, 2]) {
    const result = await page.request.post('/api/staff/questions', {
      headers: { 'X-CSRF-Token': csrf_token },
      data: {
        type: 'TRUE_FALSE',
        content: `分值核对 ${suffix}-${index}`,
        options: [],
        standard_answer: false,
        explanation: null,
        subject: '数学',
        knowledge_tags: [],
        difficulty: 'MEDIUM',
      },
    })
    expect(result.ok()).toBeTruthy()
  }
  await page.goto('/staff/papers')
  await page.getByRole('button', { name: '新建试卷' }).click()
  await page.getByLabel('试卷名称').fill(`分值试卷 ${suffix}`)
  await page.getByLabel('搜索可用题目').fill(String(suffix))
  await page.getByRole('button', { name: '查询可用题目' }).click()
  for (const index of [1, 2]) {
    await page
      .getByRole('row')
      .filter({ hasText: `分值核对 ${suffix}-${index}` })
      .getByRole('button', { name: '加入', exact: true })
      .click()
  }
  const selected = page.getByTestId('selected-questions')
  await page.getByLabel('搜索可用题目').fill(`${suffix}-1`)
  await page.getByLabel('搜索可用题目').press('Enter')
  await expect(page.getByRole('row').filter({ hasText: `分值核对 ${suffix}-2` })).toBeHidden()
  await expect(page.getByRole('dialog')).toBeVisible()
  await selected.getByLabel('第 1 题分值').fill('2.5')
  await selected.getByLabel('第 2 题分值').fill('3.5')
  await expect(page.getByRole('status', { name: '试卷分值汇总' })).toHaveText(
    '2 道题 · 总分 6.0 分',
  )
  await selected.getByRole('button', { name: '上移第 2 题' }).click()
  await page.getByRole('button', { name: '保存试卷' }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
  const row = page.getByRole('row').filter({ hasText: `分值试卷 ${suffix}` })
  await row.getByRole('button', { name: '编辑', exact: true }).click()
  await expect(selected.locator('article').first()).toContainText(`分值核对 ${suffix}-2`)
  await expect(selected.getByLabel('第 1 题分值')).toHaveValue('3.5')
})

test('考试草稿跨设置、快照和资格分区切换时保留修改，保存后可重新读取', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
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
      content: `跨区原题 ${suffix}`,
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
    data: { title: `跨区试卷 ${suffix}`, questions: [{ question_id: question.id, score: '2.5' }] },
  })
  expect(paperResponse.ok()).toBeTruthy()
  const paper = await paperResponse.json()
  const examResponse = await page.request.post('/api/staff/exams', {
    headers,
    data: { title: `跨区考试 ${suffix}`, source_paper_id: paper.id, audience_type: 'RESTRICTED' },
  })
  expect(examResponse.ok()).toBeTruthy()
  const exam = await examResponse.json()
  await page.goto(`/staff/exams/${exam.id}`)
  await page.getByRole('tab', { name: '考试设置', exact: true }).click()
  await page.getByLabel('考试说明', { exact: true }).fill('设置与快照应一起保存')
  await page.getByLabel('作答时长（分钟）').fill('45')
  await page.getByRole('tab', { name: '题目快照', exact: true }).click()
  await page.getByRole('button', { name: '编辑快照第 1 题' }).click()
  await page.getByLabel('题干', { exact: true }).fill(`跨区修改 ${suffix}`)
  await page.getByRole('button', { name: '应用题目修改' }).click()
  await page.getByLabel('快照第 1 题分值').fill('3.5')
  await page.getByRole('tab', { name: '参考资格', exact: true }).click()
  await page.getByRole('tab', { name: '考试设置', exact: true }).click()
  await expect(page.getByLabel('考试说明', { exact: true })).toHaveValue('设置与快照应一起保存')
  await expect(page.getByLabel('作答时长（分钟）')).toHaveValue('45')
  await page.getByLabel('考试名称', { exact: true }).fill('')
  await page.getByRole('tab', { name: '题目快照', exact: true }).click()
  await page.getByRole('button', { name: '保存考试草稿' }).click()
  await expect(page.getByRole('tab', { name: '考试设置', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(page.getByLabel('考试名称', { exact: true })).toBeFocused()
  await page.getByLabel('考试名称', { exact: true }).fill(`跨区考试 ${suffix}`)
  await page.getByRole('button', { name: '保存考试草稿' }).click()
  await expect(page.getByText('考试草稿已保存', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('考试说明', { exact: true })).toHaveValue('设置与快照应一起保存')
  await page.getByRole('tab', { name: '题目快照', exact: true }).click()
  await expect(page.getByTestId('exam-snapshot')).toContainText(`跨区修改 ${suffix}`)
  await expect(page.getByLabel('快照第 1 题分值')).toHaveValue('3.5')
})
