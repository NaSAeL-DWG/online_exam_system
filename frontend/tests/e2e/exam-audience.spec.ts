import { expect, test } from '@playwright/test'

test('教师配置阅卷教师并合并班级名单，撤销资格后重复补入不会恢复', async ({ page }) => {
  test.setTimeout(60_000)
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.goto('/login')
  await page.getByLabel('登录账号').fill(process.env.E2E_ADMIN_LOGIN!)
  await page.getByLabel('密码').fill(process.env.E2E_ADMIN_PASSWORD!)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/home')
  const { csrf_token } = await (await page.request.get('/api/auth/csrf')).json()
  const headers = { 'X-CSRF-Token': csrf_token }
  const suffix = Date.now().toString().slice(-9)
  const teacherNo = `ET${suffix}`
  const studentNo = `ES${suffix}`
  const teacherResponse = await page.request.post('/api/admin/teachers', {
    headers,
    data: {
      teacher_no: teacherNo,
      real_name: `阅卷教师${suffix}`,
      email: `teacher-${suffix}@example.com`,
      phone_number: `138${suffix.slice(-8)}`,
      temporary_password: 'Teacher123!',
    },
  })
  expect(teacherResponse.ok()).toBeTruthy()
  expect(
    (
      await page.request.post('/api/auth/register', {
        headers,
        data: {
          student_no: studentNo,
          real_name: `名单学生${suffix}`,
          email: `student-${suffix}@example.com`,
          phone_number: `139${suffix.slice(-8)}`,
          password: 'Student123!',
        },
      })
    ).ok(),
  ).toBeTruthy()
  const reviews = await (
    await page.request.get(`/api/staff/reviews?q=${studentNo}&page=1&page_size=20`)
  ).json()
  const review = reviews.items[0]
  expect(
    (
      await page.request.post(`/api/staff/reviews/${review.id}/decision`, {
        headers,
        data: { decision: 'APPROVED' },
      })
    ).ok(),
  ).toBeTruthy()
  for (const index of [1, 2]) {
    const response = await page.request.post('/api/classes', {
      headers,
      data: { name: `名单班 ${suffix}-${index}`, description: '', teacher_ids: [] },
    })
    expect(response.ok()).toBeTruthy()
    const { class_info } = await response.json()
    expect(
      (
        await page.request.put(`/api/classes/${class_info.id}/members/${review.user.id}`, {
          headers,
          data: { role: 'STUDENT' },
        })
      ).ok(),
    ).toBeTruthy()
  }
  const questionResponse = await page.request.post('/api/staff/questions', {
    headers,
    data: {
      type: 'SHORT_ANSWER',
      content: `简答 ${suffix}`,
      options: [],
      standard_answer: null,
      subject: '语文',
      knowledge_tags: [],
      difficulty: 'MEDIUM',
    },
  })
  expect(questionResponse.ok()).toBeTruthy()
  const question = await questionResponse.json()
  const paperResponse = await page.request.post('/api/staff/papers', {
    headers,
    data: { title: `名单试卷 ${suffix}`, questions: [{ question_id: question.id, score: '10.0' }] },
  })
  expect(paperResponse.ok()).toBeTruthy()
  const paper = await paperResponse.json()
  const examResponse = await page.request.post('/api/staff/exams', {
    headers,
    data: { title: `名单考试 ${suffix}`, source_paper_id: paper.id, audience_type: 'RESTRICTED' },
  })
  expect(examResponse.ok()).toBeTruthy()
  const exam = await examResponse.json()
  await page.getByRole('button', { name: '退出登录' }).click()
  await page.getByLabel('登录账号').fill(teacherNo)
  await page.getByLabel('密码').fill('Teacher123!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByLabel('当前密码').fill('Teacher123!')
  await page.getByLabel('新密码', { exact: true }).fill('Teacher456!')
  await page.getByLabel('确认新密码').fill('Teacher456!')
  await page.getByRole('button', { name: '保存新密码' }).click()
  await page.getByLabel('登录账号').fill(teacherNo)
  await page.getByLabel('密码').fill('Teacher456!')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/home')
  await page.goto(`/staff/exams/${exam.id}`)
  await page.getByLabel('搜索补入班级').fill(suffix)
  await page.getByRole('button', { name: '查询补入班级' }).click()
  for (const index of [1, 2])
    await page.getByLabel(`选择班级 名单班 ${suffix}-${index}`, { exact: true }).check()
  await page.getByLabel('搜索学生').fill(studentNo)
  await page.getByRole('button', { name: '查询学生' }).click()
  await page.getByLabel('选择学生', { exact: true }).click()
  await page.getByText(`名单学生${suffix}（${studentNo}）`, { exact: true }).click()
  await page.getByRole('button', { name: '补入参考名单' }).click()
  await expect(page.getByText('新增 1 人，已有 0 人', { exact: true })).toBeVisible()
  const participant = page
    .getByTestId('exam-participants')
    .getByRole('row')
    .filter({ hasText: studentNo })
  await participant.getByRole('button', { name: '撤销资格' }).click()
  await page.getByLabel('资格变更原因').fill('身份核验暂不通过')
  await page.getByRole('button', { name: '确认撤销资格' }).click()
  await expect(participant).toContainText('已撤销')
  await page.getByLabel(`选择班级 名单班 ${suffix}-1`, { exact: true }).check()
  await page.getByRole('button', { name: '补入参考名单' }).click()
  await expect(page.getByText(/1 人的资格已撤销，需显式恢复/)).toBeVisible()
  await expect(participant).toContainText('已撤销')
  await participant.getByRole('button', { name: '恢复资格' }).click()
  await page.getByLabel('资格变更原因').fill('核验通过恢复资格')
  await page.getByRole('button', { name: '确认恢复资格' }).click()
  await expect(participant).toContainText('有效资格')
  await expect(page.getByText(/1 人的资格已撤销，需显式恢复/)).toBeHidden()
  await page.getByLabel('开始时间（上海）').fill('2030-01-01T09:00')
  await page.getByLabel('结束时间（上海）').fill('2030-01-01T11:00')
  await page.getByLabel('作答时长（分钟）').fill('60')
  await page.getByRole('button', { name: '保存考试草稿' }).click()
  await expect(page.getByText('考试草稿已保存', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '发布考试', exact: true }).click()
  await page.getByRole('button', { name: '确认发布' }).click()
  await expect(page.getByRole('alert').filter({ hasText: '含简答题须指定' })).toBeVisible()
  await page.getByLabel('搜索教师').fill(teacherNo)
  await page.getByRole('button', { name: '查询教师' }).click()
  await page.getByLabel('负责教师').click()
  await page.getByText(`阅卷教师${suffix}（${teacherNo}）`, { exact: true }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: '保存考试草稿' })).toBeEnabled()
  await page.getByRole('button', { name: '保存考试草稿' }).click()
  await expect(page.getByText('考试草稿已保存', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '发布考试', exact: true }).click()
  await page.getByRole('button', { name: '确认发布' }).click()
  await expect(page.getByText('已发布', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('dialog')).toBeHidden()
  await page.screenshot({ path: 'test-results/visual/exam-participants.png', fullPage: true })
})
