import { expect, test } from '@playwright/test'

test('学生注册后可以看到待审核申请', async ({ page }) => {
  const suffix = Date.now().toString().slice(-8)

  await page.goto('/register')
  await page.getByLabel('姓名').fill('测试学生')
  await page.getByLabel('学号').fill(`S${suffix}`)
  await page.getByLabel('邮箱').fill(`student-${suffix}@example.com`)
  await page.getByLabel('手机号').fill(`139${suffix}`)
  await page.getByLabel('密码', { exact: true }).fill('Student123!')
  await page.getByLabel('确认密码').fill('Student123!')
  await page.getByRole('button', { name: '提交注册' }).click()

  await expect(page.getByText('申请已提交', { exact: true })).toBeVisible()
  await expect(page.getByText('等待教师审核')).toBeVisible()
})
