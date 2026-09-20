import { expect, test } from '@playwright/test'

const adminLogin = process.env.E2E_ADMIN_LOGIN
const adminPassword = process.env.E2E_ADMIN_PASSWORD

test('管理员创建的教师首次登录必须修改临时密码', async ({ page }) => {
  test.skip(!adminLogin || !adminPassword, '需要 .local/e2e.env 中的管理员测试凭据')
  const suffix = Date.now().toString().slice(-8)
  const teacherNo = `T${suffix}`
  const temporaryPassword = 'Teacher123!'
  const newPassword = 'Teacher456!'

  await page.goto('/login')
  await page.getByLabel('登录账号').fill(adminLogin!)
  await page.getByLabel('密码').fill(adminPassword!)
  await page.getByRole('button', { name: '登录' }).click()
  await page.getByText('账号管理', { exact: true }).click()

  await page.getByRole('button', { name: '新建教师' }).click()
  await page.getByLabel('工号').fill(teacherNo)
  await page.getByLabel('姓名').fill('流程测试教师')
  await page.getByLabel('邮箱').fill(`teacher-${suffix}@example.com`)
  await page.getByLabel('手机号').fill(`138${suffix}`)
  await page.getByLabel('临时密码').fill(temporaryPassword)
  await page.getByRole('button', { name: '创建教师' }).click()
  await expect(page.getByText(teacherNo, { exact: true })).toBeVisible()

  await page.getByRole('button', { name: '退出登录' }).click()
  await page.getByLabel('登录账号').fill(teacherNo)
  await page.getByLabel('密码').fill(temporaryPassword)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '请先修改临时密码' })).toBeVisible()

  await page.getByLabel('当前密码').fill(temporaryPassword)
  await page.getByLabel('新密码', { exact: true }).fill(newPassword)
  await page.getByLabel('确认新密码').fill(newPassword)
  await page.getByRole('button', { name: '保存新密码' }).click()

  await expect(page.getByRole('heading', { name: '欢迎回来' })).toBeVisible()
  await page.getByLabel('登录账号').fill(teacherNo)
  await page.getByLabel('密码').fill(newPassword)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '教师工作台' })).toBeVisible()
  await expect(page.locator('.n-message')).toHaveCount(0, { timeout: 5_000 })
  await page.screenshot({ path: 'test-results/visual/teacher-workbench.png', fullPage: true })
})
