import { expect, test } from '@playwright/test'
import { apiWrite, gradingFixture, waitForTask } from './grading-fixtures'
import { delayNextResponse, nextPaint, refreshOnFocus } from './results-boundaries-helpers'
import { publishFixture, resultsFixture } from './results-fixtures'

test.beforeEach(async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.goto('/login')
  await apiWrite(page.request, '/auth/login', {
    login_name: process.env.E2E_ADMIN_LOGIN,
    password: process.env.E2E_ADMIN_PASSWORD,
  })
  await page.goto('/home')
})

test('公布前置条件失败时教师得到真实原因且界面不报告成功', async ({ page, browser }, testInfo) => {
  test.setTimeout(90_000)
  const ongoing = await resultsFixture(page, browser, { endsInSeconds: 60 })
  try {
    await page.goto(`/staff/exams/${ongoing.exam.id}`)
    await page.getByRole('button', { name: '公布整场结果', exact: true }).click()
    const rejected = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/api/staff/exams/${ongoing.exam.id}/publish-results`) &&
        response.request().method() === 'POST',
    )
    await page.getByRole('button', { name: '确认公布结果', exact: true }).click()
    const earlyResponse = await rejected
    expect(earlyResponse.status()).toBe(409)
    expect((await earlyResponse.json()).detail.code).toBe('RESULTS_NOT_READY')
    await expect(page.getByText('考试结束后才能公布结果', { exact: true })).toBeVisible()
    await expect(page.getByText('结果已公布', { exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '确认公布结果', exact: true })).toBeEnabled()
    await expect(page.getByRole('button', { name: '撤回已公布结果', exact: true })).toHaveCount(0)
    await page.screenshot({
      path: testInfo.outputPath('publish-before-end-rejected.png'),
      fullPage: true,
    })
    await page.getByRole('button', { name: '暂不公布', exact: true }).click()
  } finally {
    await ongoing.context.close()
  }

  // 第二场已结束，但有效简答仍未阅完；拒绝原因由真实服务端产生。
  const pending = await gradingFixture(page, browser, 3)
  await waitForTask(page, pending.exam.id, pending.attemptId)
  await page.goto(`/staff/exams/${pending.exam.id}`)
  await page.getByRole('button', { name: '公布整场结果', exact: true }).click()
  const rejected = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/api/staff/exams/${pending.exam.id}/publish-results`) &&
      response.request().method() === 'POST',
  )
  await page.getByRole('button', { name: '确认公布结果', exact: true }).click()
  const pendingResponse = await rejected
  expect(pendingResponse.status()).toBe(409)
  expect((await pendingResponse.json()).detail.code).toBe('RESULTS_NOT_READY')
  await expect(
    page.getByText('全部有效作答须提交并按当前评分依据完成判分', { exact: true }),
  ).toBeVisible()
  await expect(page.getByText('结果已公布', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '确认公布结果', exact: true })).toBeEnabled()
  await expect(page.getByRole('button', { name: '撤回已公布结果', exact: true })).toHaveCount(0)
  await page.screenshot({
    path: testInfo.outputPath('publish-pending-grading-rejected.png'),
    fullPage: true,
  })
})

test('撤回后的新读取完成后迟到的真实成绩和答卷响应不能恢复旧内容', async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(90_000)
  const fixture = await resultsFixture(page, browser)
  const published = await publishFixture(page, fixture)
  const resultPage = await fixture.context.newPage()
  const reviewPage = await fixture.context.newPage()
  const resultPath = `/api/student/results/${fixture.exam.id}`
  const reviewPath = `/api/student/attempts/${fixture.firstId}/review`
  try {
    await resultPage.goto(`/student/results/${fixture.exam.id}`)
    await expect(resultPage.getByRole('region', { name: '最终成绩' })).toContainText('2.5')
    await reviewPage.goto(`/student/attempts/${fixture.firstId}/review`)
    await expect(reviewPage.getByText(fixture.questions[0].content, { exact: true })).toBeVisible()
    await expect(
      reviewPage.getByText(fixture.questions[0].explanation, { exact: true }),
    ).toBeVisible()

    const oldResult = await delayNextResponse(resultPage, resultPath)
    const oldReview = await delayNextResponse(reviewPage, reviewPath)
    try {
      await resultPage.getByRole('button', { name: '刷新结果', exact: true }).click()
      const capturedResult = await oldResult.ready
      expect(capturedResult.status()).toBe(200)
      expect((await capturedResult.json()).final_score).toBe('2.5')
      await reviewPage.getByRole('button', { name: '刷新答卷', exact: true }).click()
      const capturedReview = await oldReview.ready
      expect(capturedReview.status()).toBe(200)
      expect((await capturedReview.json()).questions[0].standard_answer).toBe(true)

      await apiWrite(page.request, `/staff/exams/${fixture.exam.id}/withdraw-results`, {
        version: published.version,
        reason: '独立验收：旧响应仍在网络中时撤回。',
      })
      const freshResult = resultPage.waitForResponse(
        (response) => response.url().endsWith(resultPath) && response.status() === 200,
      )
      await refreshOnFocus(resultPage)
      expect((await (await freshResult).json()).result_state).toBe('CORRECTING')
      await expect(resultPage.getByText('结果更正中', { exact: true }).first()).toBeVisible()
      const freshReview = reviewPage.waitForResponse(
        (response) => response.url().endsWith(reviewPath) && response.status() === 403,
      )
      await refreshOnFocus(reviewPage)
      await freshReview
      await expect(reviewPage.getByText('暂无可查看的答卷。', { exact: true })).toBeVisible()

      // 新的真实授权读取已完成，现在原样交付此前缓冲的两个 200 响应。
      await Promise.all([oldResult.deliver(), oldReview.deliver()])
      await Promise.all([nextPaint(resultPage), nextPaint(reviewPage)])
      await expect(resultPage.getByText('结果更正中', { exact: true }).first()).toBeVisible()
      await expect(resultPage.getByRole('region', { name: '最终成绩' })).toHaveCount(0)
      await expect(resultPage.getByRole('link', { name: '回看答卷', exact: true })).toHaveCount(0)
      await expect(reviewPage.getByRole('region', { name: '答卷得分' })).toHaveCount(0)
      await expect(reviewPage.getByText(fixture.questions[0].content, { exact: true })).toHaveCount(
        0,
      )
      await expect(
        reviewPage.getByText(fixture.questions[0].explanation, { exact: true }),
      ).toHaveCount(0)
      await expect(reviewPage.getByText('暂无可查看的答卷。', { exact: true })).toBeVisible()
      await resultPage.screenshot({
        path: testInfo.outputPath('late-result-remains-hidden.png'),
        fullPage: true,
      })
      await reviewPage.screenshot({
        path: testInfo.outputPath('late-review-remains-hidden.png'),
        fullPage: true,
      })
    } finally {
      oldResult.release()
      oldReview.release()
    }
  } finally {
    await fixture.context.close()
  }
})

test('禁止回看的已公布考试只显示总分且所有学生页面隐藏题目反馈细节', async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(90_000)
  const fixture = await resultsFixture(page, browser, { allowReview: false })
  await publishFixture(page, fixture)
  const staffAttempt = await page.request.get(`/api/staff/attempts/${fixture.firstId}`)
  expect(staffAttempt.ok()).toBeTruthy()
  const answerId = (await staffAttempt.json()).questions[0].answer.id as string
  const studentPage = await fixture.context.newPage()
  try {
    await studentPage.goto(`/student/results/${fixture.exam.id}`)
    await expect(studentPage.getByRole('region', { name: '最终成绩' })).toContainText('2.5')
    await expect(studentPage.getByText(/本场未开放答卷回看/)).toBeVisible()
    await expect(studentPage.getByRole('link', { name: '回看答卷', exact: true })).toHaveCount(0)

    // 即使学生保存过答卷或答案地址，直接导航也不能绕过回看设置。
    await studentPage.goto(`/student/attempts/${fixture.firstId}/review`)
    await expect(studentPage.getByText('本场考试不允许回看答卷', { exact: true })).toBeVisible()
    await expect(studentPage.getByText('暂无可查看的答卷。', { exact: true })).toBeVisible()
    await expect(studentPage.getByRole('region', { name: '答卷得分' })).toHaveCount(0)
    for (const question of fixture.questions) {
      await expect(studentPage.getByText(question.content, { exact: true })).toHaveCount(0)
      await expect(studentPage.getByText(question.explanation, { exact: true })).toHaveCount(0)
    }
    await studentPage.goto('/student/mistakes')
    await expect(studentPage.getByText('暂无符合条件的错题。', { exact: true })).toBeVisible()
    await expect(studentPage.getByRole('link', { name: '查看错题', exact: true })).toHaveCount(0)
    await studentPage.goto(`/student/mistakes/${answerId}`)
    await expect(studentPage.getByText('暂无可查看的错题。', { exact: true })).toBeVisible()
    await expect(studentPage.getByLabel('学习备注')).toHaveCount(0)
    await expect(
      studentPage.getByRole('button', { name: '保存学习标记', exact: true }),
    ).toHaveCount(0)

    await studentPage.goto('/home')
    await studentPage
      .getByRole('navigation', { name: '主导航' })
      .getByRole('link', { name: '学习分析', exact: true })
      .click()
    await expect(
      studentPage.getByRole('img', { name: '最终得分率趋势图' }).locator('svg'),
    ).toBeVisible()
    await studentPage.getByText('查看趋势数据', { exact: true }).click()
    await expect(
      studentPage.getByRole('row', { name: new RegExp(`${fixture.exam.title}.*2.5.*16.7%`) }),
    ).toBeVisible()
    await expect(studentPage.getByText('暂无允许回看的题型数据。', { exact: true })).toBeVisible()
    await expect(studentPage.getByText('暂无可见的知识点错题记录。', { exact: true })).toBeVisible()
    await expect(studentPage.getByRole('img', { name: '题型得分率图' })).toHaveCount(0)
    await expect(studentPage.getByRole('img', { name: '知识点错题分布图' })).toHaveCount(0)
    await expect(studentPage.getByText('查看题型数据', { exact: true })).toHaveCount(0)
    await expect(studentPage.getByText('查看知识点数据', { exact: true })).toHaveCount(0)
    await expect(studentPage.getByText('函数', { exact: true })).toHaveCount(0)
    await expect(studentPage.getByText('代数', { exact: true })).toHaveCount(0)
    for (const question of fixture.questions) {
      await expect(studentPage.getByText(question.content, { exact: true })).toHaveCount(0)
      await expect(studentPage.getByText(question.explanation, { exact: true })).toHaveCount(0)
    }
    await studentPage.screenshot({
      path: testInfo.outputPath('no-review-analysis-scope.png'),
      fullPage: true,
    })
    await studentPage.goto(`/student/results/${fixture.exam.id}`)
    await expect(studentPage.getByRole('region', { name: '最终成绩' })).toContainText('2.5')
    await studentPage.screenshot({
      path: testInfo.outputPath('no-review-total-score-visible.png'),
      fullPage: true,
    })
  } finally {
    await fixture.context.close()
  }
})
