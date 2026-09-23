import { expect, test } from '@playwright/test'

const adminLogin = process.env.E2E_ADMIN_LOGIN
const adminPassword = process.env.E2E_ADMIN_PASSWORD

test('学生被拒绝后可以更正资料并重新提交审核', async ({ page }) => {
  test.skip(!adminLogin || !adminPassword, '需要 .local/e2e.env 中的管理员测试凭据')
  const suffix = Date.now().toString().slice(-8)
  const studentNo = `S${suffix}`
  const studentPassword = 'Student123!'

  await page.goto('/register')
  await page.getByLabel('姓名').fill('待更正学生')
  await page.getByLabel('学号').fill(studentNo)
  await page.getByLabel('邮箱').fill(`student-${suffix}@example.com`)
  await page.getByLabel('手机号').fill(`135${suffix}`)
  await page.getByLabel('密码', { exact: true }).fill(studentPassword)
  await page.getByLabel('确认密码').fill(studentPassword)
  await page.getByRole('button', { name: '提交注册' }).click()

  await page.getByRole('button', { name: '登录查看审核状态' }).click()
  await page.getByLabel('登录账号').fill(adminLogin!)
  await page.getByLabel('密码').fill(adminPassword!)
  await page.getByRole('button', { name: '登录' }).click()
  await page.getByText('学生审核', { exact: true }).click()
  await page.getByLabel('搜索申请').fill(studentNo)
  await page.getByRole('button', { name: '查询申请' }).click()

  const row = page.getByRole('row').filter({ hasText: studentNo })
  await row.getByRole('button', { name: '拒绝' }).click()
  await page.getByLabel('拒绝原因').fill('请核对真实姓名')
  await page.getByRole('button', { name: '确认拒绝' }).click()
  await expect(row.getByText('已拒绝')).toBeVisible()

  await page.getByRole('button', { name: '退出登录' }).click()
  await page.getByLabel('登录账号').fill(studentNo)
  await page.getByLabel('密码').fill(studentPassword)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText('申请未通过', { exact: true })).toBeVisible()
  await page.getByLabel('姓名').fill('已更正学生')
  await page.getByRole('button', { name: '重新提交审核' }).click()
  await expect(page.getByText('申请审核中', { exact: true })).toBeVisible()
  await expect(page.locator('.n-message')).toHaveCount(0, { timeout: 5_000 })
  await page.screenshot({ path: 'test-results/visual/student-application.png', fullPage: true })
})
