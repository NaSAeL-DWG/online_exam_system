import { expect, test } from '@playwright/test'

test('真实服务的21名教师可分页查询并跨页关联教学班', async ({ page }) => {
  test.setTimeout(120_000)
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
  await page.getByLabel('密码').fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '管理工作台' })).toBeVisible()
  const prefix = `P${Date.now()}`
  const csrf = await page.request.get('/api/auth/csrf')
  const { csrf_token: csrfToken } = await csrf.json()
  for (let index = 0; index < 21; index += 1) {
    const number = String(index).padStart(2, '0')
    const response = await page.request.post('/api/admin/teachers', {
      headers: { 'X-CSRF-Token': csrfToken },
      data: {
        teacher_no: `${prefix}${number}`,
        real_name: `分页教师${number}`,
        email: `${prefix}${number}@example.com`,
        phone_number: '13800000000',
        temporary_password: 'Teacher123!',
      },
    })
    expect(response.status()).toBe(201)
  }
  await page.getByText('账号管理', { exact: true }).click()
  await page.getByLabel('搜索账号').fill(prefix)
  await page.getByRole('button', { name: '查询账号' }).click()
  await expect(page.getByText('共 21 条 · 第 1 / 2 页')).toBeVisible()
  await expect(page.getByRole('row').filter({ hasText: prefix })).toHaveCount(20)
  await page.getByRole('button', { name: '账号下一页' }).click()
  await expect(page.getByRole('row').filter({ hasText: prefix })).toHaveCount(1)
  await expect(page.getByRole('row').filter({ hasText: `${prefix}00` })).toBeVisible()

  await page.getByText('教学班', { exact: true }).click()
  await page.getByRole('button', { name: '新建教学班' }).click()
  await page.getByLabel('教学班名称').fill(`跨页教学班 ${prefix}`)
  await page.getByLabel('搜索教师').fill(prefix)
  await page.getByRole('button', { name: '查询教师' }).click()
  await page.getByLabel('负责教师').click()
  await page.getByText(`分页教师20（${prefix}20）`, { exact: true }).click()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '教师候选下一页' }).click()
  await page.getByLabel('负责教师').click()
  await page.getByText(`分页教师00（${prefix}00）`, { exact: true }).click()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '保存', exact: true }).click()
  const classRow = page.getByRole('row').filter({ hasText: `跨页教学班 ${prefix}` })
  await expect(classRow).toContainText('分页教师20')
  await expect(classRow).toContainText('分页教师00')
  await classRow.getByRole('button', { name: '编辑', exact: true }).click()
  await expect(page.getByLabel('负责教师')).toContainText(`分页教师00（${prefix}00）`)
  await expect(page.getByLabel('负责教师')).toContainText(`分页教师20（${prefix}20）`)
  await expect(page.locator('.n-message')).toHaveCount(0, { timeout: 5_000 })
  await page.screenshot({
    path: 'test-results/visual/member-pagination.png',
    fullPage: true,
    animations: 'disabled',
  })
})
