import { expect, test, type Page } from '@playwright/test'

const adminLogin = process.env.E2E_ADMIN_LOGIN
const adminPassword = process.env.E2E_ADMIN_PASSWORD

async function login(page: Page, loginName: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(loginName)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
}

test('管理员可创建多教师教学班、维护学生并归档', async ({ page }) => {
  test.skip(!adminLogin || !adminPassword, '需要 .local/e2e.env 中的管理员测试凭据')
  const suffix = Date.now().toString().slice(-8)
  const studentNo = `C${suffix}`
  const studentPassword = 'Student123!'
  const className = `软件测试 ${suffix}`

  await page.goto('/register')
  await page.getByLabel('姓名').fill('班级流程学生')
  await page.getByLabel('学号').fill(studentNo)
  await page.getByLabel('邮箱').fill(`class-student-${suffix}@example.com`)
  await page.getByLabel('手机号').fill(`137${suffix}`)
  await page.getByLabel('密码', { exact: true }).fill(studentPassword)
  await page.getByLabel('确认密码').fill(studentPassword)
  await page.getByRole('button', { name: '提交注册' }).click()

  await login(page, adminLogin!, adminPassword!)
  await page.getByText('学生审核', { exact: true }).click()
  await page.getByLabel('搜索申请').fill(studentNo)
  await page.getByRole('button', { name: '查询申请' }).click()
  await page
    .getByRole('row')
    .filter({ hasText: studentNo })
    .getByRole('button', { name: '通过' })
    .click()

  const csrf = await page.request.get('/api/auth/csrf')
  const { csrf_token: csrfToken } = (await csrf.json()) as { csrf_token: string }
  const teacherNames = [`甲教师${suffix}`, `乙教师${suffix}`]
  for (const [index, realName] of teacherNames.entries()) {
    const response = await page.request.post('/api/admin/teachers', {
      headers: { 'X-CSRF-Token': csrfToken },
      data: {
        teacher_no: `C${index}${suffix}`,
        real_name: realName,
        email: `class-teacher-${index}-${suffix}@example.com`,
        phone_number: `136${index}${suffix.slice(1)}`,
        temporary_password: 'Teacher123!',
      },
    })
    expect(response.ok()).toBeTruthy()
  }

  await page.getByText('教学班', { exact: true }).click()
  await page.getByRole('button', { name: '新建教学班' }).click()
  await page.getByLabel('教学班名称').fill(className)
  await page.getByLabel('说明').fill('真实 API 浏览器流程创建')
  await page.getByLabel('搜索教师').fill(suffix)
  await page.getByRole('button', { name: '查询教师' }).click()
  await page.getByLabel('负责教师').click()
  for (const teacherName of teacherNames) {
    await page.getByText(teacherName, { exact: false }).click()
  }
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '保存' }).click()

  const classRow = page.getByRole('row').filter({ hasText: className })
  await expect(classRow).toContainText(teacherNames[0])
  await expect(classRow).toContainText(teacherNames[1])
  await classRow.getByRole('button', { name: '成员管理' }).click()
  await page.getByLabel('搜索学生').fill(studentNo)
  await page.getByRole('button', { name: '查询学生' }).click()
  await page.getByLabel('选择学生').click()
  await page.getByText(`班级流程学生（${studentNo}）`).click()
  await page.getByRole('button', { name: '加入学生' }).click()
  await expect(page.getByRole('row').filter({ hasText: studentNo })).toBeVisible()

  await page.keyboard.press('Escape')
  await classRow.getByRole('button', { name: '编辑' }).click()
  await page.getByRole('button', { name: '归档教学班' }).click()
  await page.getByRole('button', { name: '确认归档' }).click()
  await expect(classRow.getByText('已归档')).toBeVisible()
  await expect(page.getByRole('dialog')).toBeHidden()
  await expect(page.locator('.n-message')).toHaveCount(0, { timeout: 5_000 })
  await page.screenshot({ path: 'test-results/visual/class-management.png', fullPage: true })
})
