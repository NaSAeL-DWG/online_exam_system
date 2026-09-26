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

test('教师编辑选择题和简答题时可安全预览 Markdown 与公式', async ({ page }) => {
  test.skip(!adminLogin || !adminPassword, '需要管理员测试凭据')
  await login(page)
  await page.goto('/staff/questions')
  await page.getByRole('button', { name: '新建题目' }).click()
  await page.getByLabel('题型', { exact: true }).selectOption('MULTIPLE_CHOICE')
  await page.getByLabel('科目', { exact: true }).fill('数学')
  const title = `安全预览 ${Date.now()}`
  await page
    .getByLabel('题干', { exact: true })
    .fill(
      `${title}\n\n**选择正数** $\\sqrt{\\frac{x^2}{2}}$\n\n<script>window.__unsafe = true</script>\n\n![外链](https://example.com/tracker.png)`,
    )
  await page.getByLabel('选项 1', { exact: true }).fill('1')
  await page.getByLabel('选项 2', { exact: true }).fill('2')
  await page.getByLabel('正确选项 1', { exact: true }).check()
  await page.getByLabel('正确选项 2', { exact: true }).check()
  await page.getByLabel('知识点标签').fill('正数,公式')
  const preview = page.getByTestId('question-preview')
  await expect(preview.locator('strong')).toHaveText('选择正数')
  await expect(preview.locator('.katex')).toBeVisible()
  await expect(preview.locator('.katex svg path')).toHaveCount(1)
  await expect(preview.locator('script')).toHaveCount(0)
  await expect(preview.locator('img')).toHaveCount(0)
  await page.getByRole('button', { name: '保存题目' }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
  await page.getByLabel('搜索题目').fill(title)
  await page.getByRole('button', { name: '查询题目' }).click()
  await page
    .getByRole('row')
    .filter({ hasText: title })
    .getByRole('button', { name: '编辑' })
    .click()
  await expect(page.getByLabel('正确选项 1', { exact: true })).toBeChecked()
  await expect(page.getByLabel('正确选项 2', { exact: true })).toBeChecked()
  await page.getByLabel('题型', { exact: true }).selectOption('SINGLE_CHOICE')
  await page.getByLabel('正确选项 1', { exact: true }).check()
  await page.getByRole('button', { name: '保存题目' }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
  await page
    .getByRole('row')
    .filter({ hasText: title })
    .getByRole('button', { name: '编辑' })
    .click()
  await page.getByLabel('题型', { exact: true }).selectOption('SHORT_ANSWER')
  await page.getByLabel('参考答案').fill('正数大于零')
  await page.getByRole('button', { name: '保存题目' }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
  await page
    .getByRole('row')
    .filter({ hasText: title })
    .getByRole('button', { name: '编辑' })
    .click()
  await expect(page.getByLabel('参考答案')).toHaveValue('正数大于零')
})

test('上传题目图片、筛选标签并检测共享编辑冲突后关闭题目', async ({ page, context }) => {
  test.skip(!adminLogin || !adminPassword, '需要管理员测试凭据')
  await login(page)
  await page.goto('/staff/questions')
  await page.getByRole('button', { name: '新建题目' }).click()
  const title = `图片版本 ${Date.now()}`
  await page.getByLabel('科目', { exact: true }).fill('几何')
  await page.getByLabel('题干', { exact: true }).fill(title)
  await page.getByLabel('知识点标签').fill(title)
  await page
    .getByLabel('上传题干图片')
    .setInputFiles({
      name: 'preview.png',
      mimeType: 'image/png',
      buffer: await page.screenshot({ clip: { x: 0, y: 0, width: 20, height: 20 } }),
    })
  const previewImage = page.getByTestId('question-preview').locator('img')
  await expect(previewImage).toHaveAttribute('src', /\/api\/assets\//)
  await expect(previewImage).toBeVisible()
  await page.getByRole('button', { name: '保存题目' }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
  await page.getByLabel('筛选知识点').fill(title)
  await page.getByRole('button', { name: '查询题目' }).click()
  const row = page.getByRole('row').filter({ hasText: title })
  await row.getByRole('button', { name: '编辑' }).click()
  const other = await context.newPage()
  await other.goto('/staff/questions')
  await other.getByLabel('搜索题目').fill(title)
  await other.getByRole('button', { name: '查询题目' }).click()
  await other
    .getByRole('row')
    .filter({ hasText: title })
    .getByRole('button', { name: '编辑' })
    .click()
  await other.getByLabel('科目', { exact: true }).fill('几何更新')
  await other.getByRole('button', { name: '保存题目' }).click()
  await expect(other.getByRole('dialog')).toBeHidden()
  await page.getByRole('button', { name: '保存题目' }).click()
  await expect(page.getByRole('button', { name: '重新加载最新题目' })).toBeVisible()
  await page.getByRole('button', { name: '重新加载最新题目' }).click()
  await expect(page.getByLabel('科目', { exact: true })).toHaveValue('几何更新')
  await page.getByRole('button', { name: '关闭题目', exact: true }).click()
  await page.getByRole('button', { name: '确认关闭' }).click()
  await expect(row).toContainText('已关闭')
  await other.close()
})
