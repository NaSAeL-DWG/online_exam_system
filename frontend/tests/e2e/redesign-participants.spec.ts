import { expect, test } from '@playwright/test'

test('参考资格先展示名单，教师按需展开补入工具', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
  await page.getByLabel('密码').fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/home')
  const { csrf_token } = await (await page.request.get('/api/auth/csrf')).json()
  const headers = { 'X-CSRF-Token': csrf_token }
  const suffix = Date.now()
  const paperResponse = await page.request.post('/api/staff/papers', {
    headers,
    data: { title: `资格入口试卷 ${suffix}`, questions: [] },
  })
  expect(paperResponse.ok()).toBeTruthy()
  const paper = await paperResponse.json()
  const examResponse = await page.request.post('/api/staff/exams', {
    headers,
    data: {
      title: `资格入口考试 ${suffix}`,
      source_paper_id: paper.id,
      audience_type: 'RESTRICTED',
    },
  })
  expect(examResponse.ok()).toBeTruthy()
  const exam = await examResponse.json()
  await page.goto(`/staff/exams/${exam.id}`)
  await page.getByRole('tab', { name: '参考资格', exact: true }).click()
  await expect(page.getByTestId('exam-participants')).toBeVisible()
  await expect(page.getByLabel('搜索补入班级')).toBeHidden()
  await page.getByRole('button', { name: '补入名单', exact: true }).click()
  await expect(page.getByLabel('搜索补入班级')).toBeVisible()
  await expect(page.getByLabel('搜索学生')).toBeVisible()
  await expect(page.getByRole('button', { name: '补入参考名单' })).toBeDisabled()
})

test('嵌套成员搜索的回车只查询候选，不会保存考试草稿', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
  await page.getByLabel('密码').fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/home')
  const { csrf_token } = await (await page.request.get('/api/auth/csrf')).json()
  const headers = { 'X-CSRF-Token': csrf_token }
  const suffix = Date.now()
  const paperResponse = await page.request.post('/api/staff/papers', {
    headers,
    data: { title: `成员查询试卷 ${suffix}`, questions: [] },
  })
  expect(paperResponse.ok()).toBeTruthy()
  const paper = await paperResponse.json()
  const title = `成员查询考试 ${suffix}`
  const examResponse = await page.request.post('/api/staff/exams', {
    headers,
    data: { title, source_paper_id: paper.id, audience_type: 'RESTRICTED' },
  })
  expect(examResponse.ok()).toBeTruthy()
  const exam = await examResponse.json()
  await page.goto(`/staff/exams/${exam.id}`)
  await page.getByLabel('考试名称').fill(`尚未保存 ${suffix}`)
  const search = page.getByLabel('搜索教师')
  await search.fill(String(suffix))
  const candidatesLoaded = page.waitForResponse(
    (response) =>
      response.url().includes(`/api/staff/teachers?`) &&
      new URL(response.url()).searchParams.get('q') === String(suffix),
  )
  await search.press('Enter')
  await candidatesLoaded
  await expect(page.getByText('有未保存修改', { exact: true })).toBeVisible()
  expect((await (await page.request.get(`/api/staff/exams/${exam.id}`)).json()).title).toBe(title)
})
