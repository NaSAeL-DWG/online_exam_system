import { expect, test } from '@playwright/test'
import { apiWrite } from './grading-fixtures'

test.use({ trace: 'off' })

test('注册非法资料在字段附近提示中文且不发送注册请求', async ({ page }) => {
  let submitted = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/api/auth/register')) submitted += 1
  })
  await page.goto('/register')
  await page.getByLabel('姓名').fill('前端校验学生')
  await page.getByLabel('学号').fill(`FV${Date.now()}`)
  await page.getByLabel('邮箱').fill('abc')
  await page.getByLabel('手机号').fill('123')
  await page.getByLabel('密码', { exact: true }).fill('short123')
  await page.getByLabel('确认密码').fill('short123')
  await page.getByRole('button', { name: '提交注册' }).click()
  await expect(page.getByLabel('邮箱')).toHaveAttribute('aria-invalid', 'true')
  await expect(page.locator('#register-email-error')).toHaveText('请输入有效的邮箱地址')
  await expect(page.locator('#register-phone_number-error')).toHaveText('至少需要5个字符')
  await expect(page.locator('#register-password-error')).toHaveText('至少需要10个字符')
  await expect(page.getByLabel('邮箱')).toBeFocused()
  await expect(page.getByLabel('邮箱')).toHaveAttribute('aria-describedby', 'register-email-error')
  expect(submitted).toBe(0)
})

test('未知字段与非标准错误响应使用中文兜底且不展示英文诊断', async ({ page }) => {
  let replies = 0
  // 仅注入外部HTTP错误契约边界；身份与字段组件不使用内部mock。
  await page.route('**/api/auth/register', async (route) => {
    replies += 1
    await route.fulfill({
      status: 422,
      contentType: 'application/json',
      body: JSON.stringify({
        detail: {
          code: 'VALIDATION_ERROR',
          message: 'Input should be valid',
          fields: replies === 1 ? { 'body.unknown_field': 'Input should be a valid string' } : null,
        },
      }),
    })
  })
  await page.goto('/register')
  await page.getByLabel('姓名').fill('兜底校验学生')
  await page.getByLabel('学号').fill(`FVU${Date.now()}`)
  await page.getByLabel('邮箱').fill('fallback@example.com')
  await page.getByLabel('手机号').fill('12345')
  await page.getByLabel('密码', { exact: true }).fill('abcdefghij')
  await page.getByLabel('确认密码').fill('abcdefghij')
  await page.getByRole('button', { name: '提交注册' }).click()
  await expect(page.locator('.form-alert')).toContainText('填写内容：内容不符合要求，请检查后重试')
  await expect(page.locator('.form-alert')).not.toContainText('Input should')
  await page.getByRole('button', { name: '提交注册' }).click()
  await expect(page.locator('.form-alert')).toContainText('请求未能完成')
})

test('密码按原始字符长度校验并保留已有凭据中的空格', async ({ page }) => {
  const loginName = `FVW${Date.now()}`
  const password = ' '.repeat(10)
  await page.goto('/register')
  await page.getByLabel('姓名').fill('字符规则学生')
  await page.getByLabel('学号').fill(loginName)
  await page.getByLabel('邮箱').fill(`${loginName}@example.com`)
  await page.getByLabel('手机号').fill('12345')
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByLabel('确认密码').fill(password)
  await page.getByRole('button', { name: '提交注册' }).click()
  await expect(page.getByRole('heading', { name: '申请已提交' })).toBeVisible()
  await page.getByRole('button', { name: '登录查看审核状态' }).click()
  await page.getByLabel('登录账号').fill(loginName)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '学生注册申请' })).toBeVisible()
})

test('只修改密码时确认字段错误与匹配指示同步更新', async ({ page }) => {
  await page.goto('/register')
  await page.getByLabel('姓名').fill('交叉校验学生')
  await page.getByLabel('学号').fill(`FVC${Date.now()}`)
  await page.getByLabel('邮箱').fill(`fvc${Date.now()}@example.com`)
  await page.getByLabel('手机号').fill('12345')
  await page.getByLabel('密码', { exact: true }).fill('abcdefghij')
  await page.getByLabel('确认密码').fill('abcdefghik')
  await page.getByRole('button', { name: '提交注册' }).click()
  await expect(page.locator('#register-confirmPassword-error')).toHaveText('两次输入的密码不一致')
  await page.getByLabel('密码', { exact: true }).fill('abcdefghik')
  await expect(page.getByText('密码已匹配', { exact: true })).toBeVisible()
  await expect(page.locator('#register-confirmPassword-error')).toHaveCount(0)
  await expect(page.getByLabel('确认密码')).toHaveAttribute('aria-invalid', 'false')
  await page.getByLabel('密码', { exact: true }).fill('anotherpassword')
  await expect(page.getByText('密码不匹配', { exact: true })).toBeVisible()
  await expect(page.locator('#register-confirmPassword-error')).toHaveText('两次输入的密码不一致')
})

test('教学班名称空白与超过200字符时就近提示并阻止创建', async ({ page }) => {
  test.skip(
    !process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD,
    '需要私有管理员测试配置',
  )
  await page.goto('/login')
  await apiWrite(page.request, '/auth/login', {
    login_name: process.env.E2E_ADMIN_LOGIN,
    password: process.env.E2E_ADMIN_PASSWORD,
  })
  await page.goto('/classes')
  await page.getByRole('button', { name: '新建教学班' }).click()
  let writes = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/api/classes')) writes += 1
  })
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.locator('#class-name-error')).toHaveText('请填写教学班名称')
  await expect(page.getByLabel('教学班名称')).toBeFocused()
  await page.getByLabel('教学班名称').fill('班'.repeat(201))
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.locator('#class-name-error')).toHaveText('最多允许200个字符')
  expect(writes).toBe(0)
})

test('拒绝审核与学生重新申请都有字段定位且非法资料不提交', async ({ page }) => {
  test.skip(
    !process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD,
    '需要私有管理员测试配置',
  )
  await page.goto('/login')
  await apiWrite(page.request, '/auth/login', {
    login_name: process.env.E2E_ADMIN_LOGIN,
    password: process.env.E2E_ADMIN_PASSWORD,
  })
  const loginName = `FVR${Date.now()}`
  const password = 'abcdefghij'
  await apiWrite(page.request, '/auth/register', {
    student_no: loginName,
    real_name: '申请校验学生',
    email: `${loginName}@example.com`,
    phone_number: '12345',
    password,
  })
  await page.goto('/staff/reviews')
  await page.getByLabel('搜索申请').fill(loginName)
  await page.getByRole('button', { name: '查询申请' }).click()
  await page
    .getByRole('row')
    .filter({ hasText: loginName })
    .getByRole('button', { name: '拒绝', exact: true })
    .click()
  await page.getByRole('button', { name: '确认拒绝' }).click()
  await expect(page.locator('#review-reason-error')).toHaveText('请填写拒绝原因')
  await expect(page.getByLabel('拒绝原因')).toBeFocused()
  await page.getByLabel('拒绝原因').fill('请核对资料后重新提交')
  await page.getByRole('button', { name: '确认拒绝' }).click()
  await expect(page.getByRole('row').filter({ hasText: loginName })).toContainText('已拒绝')
  await apiWrite(page.request, '/auth/login', { login_name: loginName, password })
  await page.goto('/student/application')
  await page.getByLabel('邮箱', { exact: true }).fill('abc')
  await page.getByLabel('手机号', { exact: true }).fill('1')
  let writes = 0
  page.on('request', (request) => {
    if (request.method() === 'PUT' && request.url().endsWith('/api/student/application'))
      writes += 1
  })
  await page.getByRole('button', { name: '重新提交审核' }).click()
  await expect(page.locator('#application-email-error')).toHaveText('请输入有效的邮箱地址')
  await expect(page.locator('#application-phone_number-error')).toHaveText('至少需要5个字符')
  expect(writes).toBe(0)
})

test('管理员创建教师、重置密码与更正账号使用就近字段校验', async ({ page }) => {
  test.skip(
    !process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD,
    '需要私有管理员测试配置',
  )
  await page.goto('/login')
  await apiWrite(page.request, '/auth/login', {
    login_name: process.env.E2E_ADMIN_LOGIN,
    password: process.env.E2E_ADMIN_PASSWORD,
  })
  await page.goto('/admin/accounts')
  await page.getByRole('button', { name: '新建教师', exact: true }).click()
  const teacherNo = `FVT${Date.now()}`
  await page.getByLabel('工号').fill(teacherNo)
  await page.getByLabel('姓名', { exact: true }).fill('教师校验用户')
  await page.getByLabel('邮箱', { exact: true }).fill('abc')
  await page.getByLabel('手机号', { exact: true }).fill('123')
  await page.getByLabel('临时密码', { exact: true }).fill('123')
  let writes = 0
  page.on('request', (request) => {
    if (
      ['POST', 'PATCH'].includes(request.method()) &&
      /\/api\/admin\/(teachers|users)/.test(request.url())
    )
      writes += 1
  })
  await page.getByRole('button', { name: '创建教师', exact: true }).click()
  await expect(page.locator('#teacher-email-error')).toHaveText('请输入有效的邮箱地址')
  await expect(page.locator('#teacher-temporary_password-error')).toHaveText('至少需要10个字符')
  expect(writes).toBe(0)
  await page.getByLabel('邮箱', { exact: true }).fill(`${teacherNo}@example.com`)
  await page.getByLabel('手机号', { exact: true }).fill('12345')
  await page.getByLabel('临时密码', { exact: true }).fill('abcdefghij')
  await page.getByRole('button', { name: '创建教师', exact: true }).click()
  await expect(page.getByText(teacherNo, { exact: true })).toBeVisible()
  await page.getByLabel('搜索账号').fill(teacherNo)
  await page.getByRole('button', { name: '查询账号' }).click()
  const row = page.getByRole('row').filter({ hasText: teacherNo })
  await row.getByRole('button', { name: '重置密码' }).click()
  await page.getByLabel('新临时密码').fill('123')
  await page.getByRole('button', { name: '确认重置' }).click()
  await expect(page.locator('#reset-temporary_password-error')).toHaveText('至少需要10个字符')
  expect(writes).toBe(1)
  await page.getByRole('button', { name: '取消', exact: true }).click()
  await row.getByRole('button', { name: '更正', exact: true }).click()
  await page.getByLabel('姓名', { exact: true }).fill('')
  await page.getByRole('button', { name: '保存更正' }).click()
  await expect(page.locator('#account-edit-real_name-error')).toHaveText('请填写姓名')
  expect(writes).toBe(1)
})

test('空登录不发送请求并将紧邻的学生注册入口整体右对齐', async ({ page }) => {
  let attempts = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/api/auth/login')) attempts += 1
  })
  await page.goto('/login')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.locator('#login-login_name-error')).toHaveText('请填写登录账号')
  await expect(page.getByLabel('登录账号')).toBeFocused()
  expect(attempts).toBe(0)
  const spacing = await page.locator('.auth-switch').evaluate((element) => {
    const line = element.getBoundingClientRect()
    const text = element.querySelector('span')!.getBoundingClientRect()
    const link = element.querySelector('a')!.getBoundingClientRect()
    return { gap: link.left - text.right, right: line.right - link.right }
  })
  expect(spacing.gap).toBeLessThanOrEqual(12)
  expect(Math.abs(spacing.right)).toBeLessThan(2)
})

test('学生修改密码与联系方式在本地定位非法字段且保留合法短电话', async ({ page }) => {
  await page.goto('/login')
  const loginName = `FVA${Date.now()}`
  const password = 'abcdefghij'
  await apiWrite(page.request, '/auth/register', {
    student_no: loginName,
    real_name: '账号校验学生',
    email: `${loginName}@example.com`,
    phone_number: '12345',
    password,
  })
  await apiWrite(page.request, '/auth/login', { login_name: loginName, password })
  let passwordWrites = 0
  let contactWrites = 0
  page.on('request', (request) => {
    if (request.method() !== 'PUT') return
    if (request.url().endsWith('/api/auth/password')) passwordWrites += 1
    if (request.url().endsWith('/api/auth/contacts')) contactWrites += 1
  })
  await page.goto('/account/password')
  await page.getByLabel('当前密码').fill(password)
  await page.getByLabel('新密码', { exact: true }).fill('short123')
  await page.getByLabel('确认新密码').fill('short123')
  await page.getByRole('button', { name: '保存新密码' }).click()
  await expect(page.locator('#password-new_password-error')).toHaveText('至少需要10个字符')
  await expect(page.getByLabel('新密码', { exact: true })).toBeFocused()
  expect(passwordWrites).toBe(0)
  await page.goto('/account/contacts')
  await page.getByLabel('邮箱').fill('abc')
  await page.getByLabel('手机号').fill('1')
  await page.getByLabel('当前密码').fill(password)
  await page.getByRole('button', { name: '保存联系方式' }).click()
  await expect(page.locator('#contacts-email-error')).toHaveText('请输入有效的邮箱地址')
  await expect(page.locator('#contacts-phone_number-error')).toHaveText('至少需要5个字符')
  expect(contactWrites).toBe(0)
  await page.getByLabel('邮箱').fill(`${loginName}@example.com`)
  await page.getByLabel('手机号').fill('54321')
  const saved = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' && response.url().endsWith('/api/auth/contacts'),
  )
  await page.getByRole('button', { name: '保存联系方式' }).click()
  expect((await saved).status()).toBe(200)
})

test('服务端拒绝更精细邮箱格式后仍显示中文字段身份并定位邮箱', async ({ page }) => {
  await page.goto('/register')
  await page.getByLabel('姓名').fill('服务端校验学生')
  await page.getByLabel('学号').fill(`FVB${Date.now()}`)
  await page.getByLabel('邮箱').fill('a..b@example.com')
  await page.getByLabel('手机号').fill('12345')
  await page.getByLabel('密码', { exact: true }).fill('abcdefghij')
  await page.getByLabel('确认密码').fill('abcdefghij')
  const response = page.waitForResponse(
    (value) => value.request().method() === 'POST' && value.url().endsWith('/api/auth/register'),
  )
  await page.getByRole('button', { name: '提交注册' }).click()
  expect((await response).status()).toBe(422)
  await expect(page.locator('#register-email-error')).toHaveText('请输入有效的邮箱地址')
  await expect(page.locator('.form-alert')).toContainText('邮箱：请输入有效的邮箱地址')
  await expect(page.getByLabel('邮箱')).toBeFocused()
  await expect(page.locator('.form-alert')).not.toContainText('value is not')
})

test('密码辅助指示即时更新且弱密码与5字符电话仍可合法注册', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/register')
  await page.getByLabel('密码', { exact: true }).fill('aaaaaaaaaa')
  await expect(page.getByText('密码强度：弱', { exact: true })).toBeVisible()
  await page.getByLabel('确认密码').fill('aaaaaaaaab')
  await expect(page.getByText('密码不匹配', { exact: true })).toBeVisible()
  await page.getByLabel('确认密码').fill('aaaaaaaaaa')
  await expect(page.getByText('密码已匹配', { exact: true })).toBeVisible()
  const spacing = await page.locator('.auth-switch').evaluate((element) => {
    const line = element.getBoundingClientRect()
    const text = element.querySelector('span')!.getBoundingClientRect()
    const link = element.querySelector('a')!.getBoundingClientRect()
    return { gap: link.left - text.right, right: line.right - link.right }
  })
  expect(spacing.gap).toBeGreaterThanOrEqual(4)
  expect(spacing.gap).toBeLessThanOrEqual(12)
  expect(Math.abs(spacing.right)).toBeLessThan(2)
  await page.getByLabel('姓名').fill('合理范围学生')
  await page.getByLabel('学号').fill(`FV${Date.now()}`)
  await page.getByLabel('邮箱').fill(`fv${Date.now()}@example.com`)
  await page.getByLabel('手机号').fill('12345')
  const response = page.waitForResponse(
    (value) => value.request().method() === 'POST' && value.url().endsWith('/api/auth/register'),
  )
  await page.getByRole('button', { name: '提交注册' }).click()
  expect((await response).status()).toBe(201)
  await expect(page.getByRole('heading', { name: '申请已提交' })).toBeVisible()
})
