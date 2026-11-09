import { expect, test } from '@playwright/test'

test('重选当前题型保留假值和文本答案，实际切换仍重置评分依据', async ({ page }) => {
  await page.route('**/api/auth/csrf', (route) =>
    route.fulfill({ json: { csrf_token: 'content-test-csrf' } }),
  )
  await page.route('**/api/auth/refresh', (route) => route.fulfill({ status: 401, json: {} }))
  await page.route('**/api/auth/me', (route) => route.fulfill({ status: 401, json: {} }))
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: '账号登录', exact: true })).toBeVisible()
  await page.evaluate(async () => {
    const modulePath = '/tests/e2e/c3-foundation-harness.ts'
    const { mountQuestionEditorHarness } = await import(modulePath)
    mountQuestionEditorHarness()
  })
  const type = page.getByRole('combobox', { name: '题型', exact: true })
  await type.click()
  await page.getByRole('option', { name: '判断题', exact: true }).click()
  await expect(page.getByRole('combobox', { name: '判断答案', exact: true })).toHaveText('假')
  await expect(page.getByTestId('question-model')).toContainText('"standard_answer":false')
  await page.getByRole('button', { name: '载入简答草稿', exact: true }).click()
  await type.click()
  await page.getByRole('option', { name: '简答题', exact: true }).click()
  await expect(page.getByRole('textbox', { name: '参考答案', exact: true })).toHaveValue(
    '保留原参考答案',
  )
  await type.click()
  await page.getByRole('option', { name: '单选题', exact: true }).click()
  await expect(page.getByTestId('question-model')).toContainText('"standard_answer":[]')
  await expect(page.getByRole('textbox', { name: /^选项 [12]$/ })).toHaveCount(2)
})
