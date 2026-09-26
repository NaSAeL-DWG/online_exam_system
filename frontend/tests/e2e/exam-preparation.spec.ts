import { expect, test, type Page } from '@playwright/test'

const adminLogin = process.env.E2E_ADMIN_LOGIN
const adminPassword = process.env.E2E_ADMIN_PASSWORD

async function login(page: Page): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(adminLogin!)
  await page.getByLabel('密码').fill(adminPassword!)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/home')
}

test('共享题库保存判断题的假答案并可重新读取', async ({ page }) => {
  test.skip(!adminLogin || !adminPassword, '需要管理员测试凭据')
  const content = `判断题 ${Date.now()}：零是正数。`
  await login(page)
  await page.getByText('共享题库', { exact: true }).click()
  await page.getByRole('button', { name: '新建题目' }).click()
  await page.getByLabel('题型', { exact: true }).selectOption('TRUE_FALSE')
  await page.getByLabel('题干', { exact: true }).fill(content)
  await page.getByLabel('科目', { exact: true }).fill('数学')
  await page.getByLabel('判断答案', { exact: true }).selectOption('false')
  await page.getByRole('button', { name: '保存题目' }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
  await page.getByLabel('搜索题目').fill(content)
  await page.getByRole('button', { name: '查询题目' }).click()
  await page
    .getByRole('row')
    .filter({ hasText: content })
    .getByRole('button', { name: '编辑' })
    .click()
  await expect(page.getByLabel('判断答案', { exact: true })).toHaveValue('false')
})
