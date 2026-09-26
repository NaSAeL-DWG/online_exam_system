import { expect, test } from '@playwright/test'

test('教师手动组卷、调整顺序与一位小数分值并归档试卷', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
  await page.getByLabel('密码').fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/home')
  const { csrf_token } = await (await page.request.get('/api/auth/csrf')).json()
  const suffix = Date.now()
  for (const index of [1, 2]) {
    const response = await page.request.post('/api/staff/questions', {
      headers: { 'X-CSRF-Token': csrf_token },
      data: {
        type: 'TRUE_FALSE',
        content: `组卷题 ${suffix}-${index}`,
        options: [],
        standard_answer: false,
        explanation: null,
        subject: '数学',
        knowledge_tags: [],
        difficulty: 'MEDIUM',
      },
    })
    expect(response.ok()).toBeTruthy()
  }
  await page.getByText('共享试卷', { exact: true }).click()
  await page.getByRole('button', { name: '新建试卷' }).click()
  await page.getByLabel('试卷名称').fill(`组卷 ${suffix}`)
  await page.getByLabel('搜索可用题目').fill(String(suffix))
  await page.getByRole('button', { name: '查询可用题目' }).click()
  for (const index of [1, 2])
    await page
      .getByRole('row')
      .filter({ hasText: `组卷题 ${suffix}-${index}` })
      .getByRole('button', { name: '加入' })
      .click()
  const selected = page.getByTestId('selected-questions')
  await selected.getByLabel('第 1 题分值').fill('2.5')
  await selected.getByLabel('第 2 题分值').fill('3.5')
  await selected.getByRole('button', { name: '上移第 2 题' }).click()
  await page.getByRole('button', { name: '保存试卷' }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
  const row = page.getByRole('row').filter({ hasText: `组卷 ${suffix}` })
  await expect(row).toContainText('6.0')
  await row.getByRole('button', { name: '编辑' }).click()
  await expect(selected.locator('article').first()).toContainText(`组卷题 ${suffix}-2`)
  await expect(selected.getByLabel('第 1 题分值')).toHaveValue('3.5')
  await page.getByRole('button', { name: '归档试卷', exact: true }).click()
  await page.getByRole('button', { name: '确认归档' }).click()
  await expect(row).toContainText('已归档')
})
