import { expect, test } from '@playwright/test'

test('账号列表翻页和角色筛选由服务器决定，故障后可以重试', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
  await page.getByLabel('密码').fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '管理工作台' })).toBeVisible()

  // HTTP 边界提供确定的分页数据；认证仍连接真实服务。
  let unavailable = false
  await page.route('**/api/admin/users**', async (route) => {
    if (unavailable) {
      await route.fulfill({
        status: 503,
        json: { detail: { code: 'DATABASE_UNAVAILABLE', message: '数据库暂时不可用，请稍后重试' } },
      })
      return
    }
    const query = new URL(route.request().url()).searchParams
    const second = query.get('page') === '2'
    const teacher = query.get('user_type') === 'TEACHER'
    const name = teacher ? '跨页教师' : second ? '第二页学生' : '第一页学生'
    await route.fulfill({
      json: {
        items: [
          {
            id: 'page-user',
            login_name: name,
            real_name: name,
            email: 'page@example.com',
            phone_number: '13800000000',
            user_type: teacher ? 'TEACHER' : 'STUDENT',
            status: 'ACTIVATED',
            must_change_password: false,
            created_at: '2026-01-01T00:00:00Z',
          },
        ],
        total: teacher ? 1 : 21,
        page: second ? 2 : 1,
        page_size: 20,
      },
    })
  })
  await page.getByText('账号管理', { exact: true }).click()
  await expect(page.getByRole('row').filter({ hasText: '第一页学生' })).toBeVisible()
  await page.getByRole('button', { name: '账号下一页' }).click()
  await expect(page.getByRole('row').filter({ hasText: '第二页学生' })).toBeVisible()
  await page.getByText('教师', { exact: true }).click()
  await expect(page.getByRole('row').filter({ hasText: '跨页教师' })).toBeVisible()
  unavailable = true
  await page.getByRole('button', { name: '查询账号' }).click()
  await expect(page.getByText('数据库暂时不可用，请稍后重试')).toBeVisible()
  unavailable = false
  await page.getByRole('button', { name: '重试加载' }).click()
  await expect(page.getByRole('row').filter({ hasText: '跨页教师' })).toBeVisible()
  await expect(page.getByText('数据库暂时不可用，请稍后重试')).toBeHidden()
})

test('审核列表可查询后续页申请，搜索会回到第一页', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
  await page.getByLabel('密码').fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '管理工作台' })).toBeVisible()
  await page.route('**/api/staff/reviews**', async (route) => {
    const query = new URL(route.request().url()).searchParams
    const second = query.get('page') === '2'
    const name = query.get('q') && !second ? '搜索到的申请' : second ? '第二页申请' : '第一页申请'
    await route.fulfill({
      json: {
        items: [
          {
            id: 'review-one',
            status: 'PENDING',
            reason: null,
            submitted_profile: {
              real_name: name,
              student_no: 'S01',
              email: 's@example.com',
              phone_number: '13800000000',
            },
            submitted_at: '2026-01-01T00:00:00Z',
            reviewed_at: null,
            reviewer_id: null,
          },
        ],
        total: 21,
        page: second ? 2 : 1,
        page_size: 20,
      },
    })
  })
  await page.getByText('学生审核', { exact: true }).click()
  await expect(page.getByRole('button', { name: '审核下一页' })).toBeVisible()
  await page.getByRole('button', { name: '审核下一页' }).click()
  await expect(page.getByRole('row').filter({ hasText: '第二页申请' })).toBeVisible()
  await page.getByLabel('搜索申请').fill('搜索')
  await page.getByRole('button', { name: '查询申请' }).click()
  await expect(page.getByRole('row').filter({ hasText: '搜索到的申请' })).toBeVisible()
})

test('教学班可从候选第二页选择教师，搜索不丢失已选择教师', async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
  await page.getByLabel('密码').fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '管理工作台' })).toBeVisible()
  await page.route('**/api/admin/teachers**', async (route) => {
    const query = new URL(route.request().url()).searchParams
    const second = query.get('page') === '2'
    const searching = Boolean(query.get('q'))
    await route.fulfill({
      json: {
        items: searching
          ? []
          : [
              {
                id: second ? 'teacher-two' : 'teacher-one',
                login_name: second ? 'T02' : 'T01',
                real_name: second ? '第二页教师' : '第一页教师',
                user_type: 'TEACHER',
                status: 'ACTIVATED',
              },
            ],
        total: searching ? 0 : 21,
        page: second ? 2 : 1,
        page_size: 20,
      },
    })
  })
  await page.getByText('教学班', { exact: true }).click()
  await page.getByRole('button', { name: '新建教学班' }).click()
  await page.getByLabel('负责教师').click()
  await page.getByText('第一页教师（T01）', { exact: true }).click()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '教师候选下一页' }).click()
  await page.getByLabel('负责教师').click()
  await page.getByText('第二页教师（T02）', { exact: true }).click()
  await page.keyboard.press('Escape')
  await page.getByLabel('搜索教师').fill('没有候选')
  await page.getByRole('button', { name: '查询教师' }).click()
  await expect(page.getByLabel('负责教师')).toContainText('第一页教师（T01）')
  await expect(page.getByLabel('负责教师')).toContainText('第二页教师（T02）')
})
