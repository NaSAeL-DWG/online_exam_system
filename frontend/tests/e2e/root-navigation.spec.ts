import { expect, test } from '@playwright/test'

for (const destination of ['/home', '/']) {
  test(`从登录页返回 ${destination} 时进入工作台`, async ({ page }) => {
    test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
    await page.goto(`/login?redirect=${destination}`)
    await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
    await page.getByLabel('密码', { exact: true }).fill(process.env.E2E_ADMIN_PASSWORD!)
    await page.getByRole('button', { name: '登录', exact: true }).click()

    await expect(page).toHaveURL('/home')
    await expect(page.getByRole('heading', { name: '管理工作台' })).toBeVisible()

    // 已登录时重新打开站点根地址，也应显示工作台而非空登录布局。
    await page.goto('/')
    await expect(page).toHaveURL('/home')
    await expect(page.getByRole('heading', { name: '管理工作台' })).toBeVisible()
  })
}
