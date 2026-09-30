import { expect, test, type Page } from '@playwright/test'

async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
  await page.getByLabel('密码', { exact: true }).fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/home')
}

test('登录任务以唯一主标题呈现，学生可直接进入注册', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('账号登录')
  await expect(page.getByLabel('登录账号')).toBeVisible()
  await expect(page.getByLabel('密码', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: '学生注册', exact: true }).click()
  await expect(page).toHaveURL('/register')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('学生注册')
})

test('手机用户可用键盘打开主导航并进入教学班', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.setViewportSize({ width: 390, height: 844 })
  await loginAsAdmin(page)
  const menuButton = page.getByRole('button', { name: '打开导航', exact: true })
  await menuButton.focus()
  await page.keyboard.press('Enter')
  await expect(menuButton).toHaveAttribute('aria-expanded', 'true')
  await page
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '教学班', exact: true })
    .click()
  await expect(page).toHaveURL('/classes')
  await expect(page.getByRole('heading', { name: '教学班', level: 1 })).toBeVisible()
  await expect(menuButton).toHaveAttribute('aria-expanded', 'false')
})

test('工作台的考试准备入口直接进入已实现的共享题库', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await loginAsAdmin(page)
  await page
    .getByRole('main')
    .getByRole('link', { name: /准备共享题目/ })
    .click()
  await expect(page).toHaveURL('/staff/questions')
  await expect(page.getByRole('heading', { level: 1, name: '共享题库', exact: true })).toBeVisible()
})
