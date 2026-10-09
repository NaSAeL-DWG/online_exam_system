import { expect, test, type Page, type TestInfo } from '@playwright/test'
import {
  apiWrite,
  fixturePassword,
  gradeWholeAttempt,
  gradingFixture,
  signedContext,
  waitForTask,
} from './grading-fixtures'
import { publishFixture, resultsFixture } from './results-fixtures'

/** 在既有业务流程的稳定状态下采集桌面和小屏，数据表允许局部滚动。 */
async function captureResponsive(page: Page, testInfo: TestInfo, name: string): Promise<void> {
  const widths = []
  for (const width of [1280, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
    await page.evaluate(async () => {
      window.scrollTo(0, 0)
      // 跨两帧等待 ResizeObserver 完成图表尺寸更新，避免采集旧宽度或滚动侧栏。
      await new Promise<void>((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
      )
    })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBe(width)
    widths.push({
      viewport: width,
      document: await page.evaluate(() => document.documentElement.scrollWidth),
    })
    await page.screenshot({
      path: testInfo.outputPath(`${name}-${width}.png`),
      fullPage: true,
      animations: 'disabled',
    })
  }
  await testInfo.attach(`${name}-widths`, {
    body: Buffer.from(JSON.stringify(widths)),
    contentType: 'application/json',
  })
  await page.setViewportSize({ width: 1280, height: 900 })
}

test.beforeEach(async ({ page }) => {
  test.skip(!process.env.E2E_ADMIN_LOGIN || !process.env.E2E_ADMIN_PASSWORD, '需要管理员测试凭据')
  await page.goto('/login')
  await apiWrite(page.request, '/auth/login', {
    login_name: process.env.E2E_ADMIN_LOGIN,
    password: process.env.E2E_ADMIN_PASSWORD,
  })
  await page.goto('/home')
})

test('学生历史保留各次成绩并取最后有效提交，撤回刷新清空成绩', async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(60_000)
  const fixture = await resultsFixture(page, browser, { twoAttempts: true })
  const published = await publishFixture(page, fixture)
  const studentPage = await fixture.context.newPage()
  await studentPage.goto('/home')
  await studentPage
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '考试历史', exact: true })
    .click()
  await studentPage.getByRole('link', { name: fixture.exam.title, exact: true }).click()
  await expect(studentPage.getByRole('region', { name: '最终成绩' })).toContainText('15.0')
  await expect(studentPage.getByRole('row', { name: /第 1 次.*2.5/ })).toBeVisible()
  await expect(studentPage.getByRole('row', { name: /第 2 次.*15.0/ })).toBeVisible()
  await captureResponsive(studentPage, testInfo, 'student-result-detail')
  await apiWrite(page.request, `/staff/exams/${fixture.exam.id}/withdraw-results`, {
    version: published.version,
    reason: '复核成绩。',
  })
  await studentPage.getByRole('button', { name: '刷新结果', exact: true }).click()
  await expect(studentPage.getByText('结果更正中', { exact: true }).first()).toBeVisible()
  await expect(studentPage.getByRole('region', { name: '最终成绩' })).toHaveCount(0)
  await expect(studentPage.getByRole('link', { name: '回看答卷', exact: true })).toHaveCount(0)
  await fixture.context.close()
})

test('教师将全部判完结果整场公布并能撤回重新公布', async ({ page, browser }, testInfo) => {
  test.setTimeout(60_000)
  const fixture = await gradingFixture(page, browser, 3)
  await waitForTask(page, fixture.exam.id, fixture.attemptId)
  const teacher = await signedContext(
    browser,
    new URL(page.url()).origin,
    fixture.teachers[0]!.loginName,
    fixturePassword,
  )
  await gradeWholeAttempt(teacher.request, fixture.attemptId)
  await teacher.close()
  await page.goto(`/staff/exams/${fixture.exam.id}`)
  await page.getByRole('button', { name: '公布整场结果', exact: true }).click()
  await page.getByRole('button', { name: '确认公布结果', exact: true }).click()
  await expect(page.getByText('结果已公布', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '撤回已公布结果', exact: true }).click()
  await page.getByLabel('撤回结果原因').fill('复核本场成绩后再次公布。')
  await page.getByRole('button', { name: '确认撤回结果', exact: true }).click()
  await expect(page.getByRole('button', { name: '公布整场结果', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '公布整场结果', exact: true }).click()
  await page.getByRole('button', { name: '确认公布结果', exact: true }).click()
  await expect(page.getByText('结果已公布', { exact: true })).toBeVisible()
  await captureResponsive(page, testInfo, 'published-results')
})

test('学生回看持久快照与部分得分，撤回刷新不保留答案解析', async ({ page, browser }, testInfo) => {
  test.setTimeout(60_000)
  const fixture = await resultsFixture(page, browser)
  const published = await publishFixture(page, fixture)
  const source = fixture.questions[0]
  await apiWrite(
    page.request,
    `/staff/questions/${source.id}`,
    { ...source, content: '来源题库已改动', explanation: '来源新解析', version: source.version },
    'PUT',
  )
  const studentPage = await fixture.context.newPage()
  await studentPage.goto(`/student/attempts/${fixture.firstId}/review`)
  await expect(
    studentPage.getByRole('heading', { name: fixture.exam.title, level: 1 }),
  ).toBeVisible()
  await expect(studentPage.getByText(source.content, { exact: true })).toBeVisible()
  await expect(
    studentPage.getByText('快照解析1：依据定义与计算过程。', { exact: true }),
  ).toBeVisible()
  await expect(studentPage.getByText('来源新解析', { exact: true })).toHaveCount(0)
  await expect(studentPage.getByRole('region', { name: '答卷得分' })).toContainText('2.5')
  await captureResponsive(studentPage, testInfo, 'student-review')
  await apiWrite(page.request, `/staff/exams/${fixture.exam.id}/withdraw-results`, {
    version: published.version,
    reason: '检查评分依据。',
  })
  await studentPage.getByRole('button', { name: '刷新答卷', exact: true }).click()
  await expect(studentPage.getByText('暂无可查看的答卷。', { exact: true })).toBeVisible()
  await expect(studentPage.getByText(source.content, { exact: true })).toHaveCount(0)
  await expect(
    studentPage.getByText('快照解析1：依据定义与计算过程。', { exact: true }),
  ).toHaveCount(0)
  await fixture.context.close()
})

test('错题保留前次部分得分并支持筛选备注与掌握，撤回后隐藏', async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(60_000)
  const fixture = await resultsFixture(page, browser, { twoAttempts: true })
  const published = await publishFixture(page, fixture)
  const studentPage = await fixture.context.newPage()
  await studentPage.goto('/home')
  const entry = studentPage
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '我的错题', exact: true })
  await expect(entry).toBeVisible()
  await entry.click()
  await studentPage.getByLabel('科目筛选').fill('结果学习测试')
  await studentPage.getByLabel('题型筛选').selectOption('MULTIPLE_CHOICE')
  await studentPage.getByLabel('知识点筛选').fill('函数')
  await studentPage.getByRole('button', { name: '筛选错题', exact: true }).click()
  await expect(studentPage.getByText(fixture.questions[2].content, { exact: true })).toBeVisible()
  await expect(studentPage.getByText('2.5 / 5.0 分', { exact: true })).toBeVisible()
  await studentPage.getByRole('link', { name: '查看错题', exact: true }).click()
  await studentPage.getByLabel('学习备注').fill('少选有部分分，复习两个正确条件。')
  await studentPage.getByLabel('已掌握本题').check()
  await studentPage.getByRole('button', { name: '保存学习标记', exact: true }).click()
  await expect(studentPage.getByText('学习标记已保存。', { exact: true })).toBeVisible()
  await studentPage.getByRole('button', { name: '刷新错题', exact: true }).click()
  await expect(studentPage.getByLabel('学习备注')).toHaveValue('少选有部分分，复习两个正确条件。')
  await expect(studentPage.getByLabel('已掌握本题')).toBeChecked()
  await captureResponsive(studentPage, testInfo, 'mistake-detail')
  await apiWrite(page.request, `/staff/exams/${fixture.exam.id}/withdraw-results`, {
    version: published.version,
    reason: '复核部分分。',
  })
  await studentPage.getByRole('button', { name: '刷新错题', exact: true }).click()
  await expect(studentPage.getByText('暂无可查看的错题。', { exact: true })).toBeVisible()
  await expect(studentPage.getByLabel('学习备注')).toHaveCount(0)
  await expect(studentPage.getByText(fixture.questions[2].content, { exact: true })).toHaveCount(0)
  await fixture.context.close()
})

test('教师统计按学生去重并仅采用最后提交，公开考试无缺考分母', async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(60_000)
  const fixture = await resultsFixture(page, browser, { twoAttempts: true })
  await page.goto(`/staff/exams/${fixture.exam.id}`)
  const analyticsTab = page.getByRole('tab', { name: '统计分析', exact: true })
  await expect(analyticsTab).toBeVisible()
  await analyticsTab.click()
  await expect(page.getByRole('region', { name: '人数统计' })).toContainText(/参考人数\s*1/)
  await expect(page.getByRole('region', { name: '人数统计' })).toContainText(/提交人数\s*1/)
  await expect(page.getByRole('region', { name: '作答与任务' })).toContainText(/有效作答次数\s*2/)
  await expect(page.getByRole('region', { name: '成绩指标' })).toContainText(/平均分\s*15.0/)
  await expect(
    page.getByText('公开考试无固定应考分母，不计算缺考或参考率。', { exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('row', { name: /第 1 题.*100.0%/ })).toBeVisible()
  await expect(page.getByRole('img', { name: '最终成绩分布图' }).locator('svg')).toBeVisible()
  await captureResponsive(page, testInfo, 'teacher-analytics')
  const source = await (await page.request.get(`/api/staff/exams/${fixture.exam.id}`)).json()
  const empty = await apiWrite(page.request, '/staff/exams', {
    title: `无样本统计 ${Date.now()}`,
    source_paper_id: source.source_paper_id,
    audience_type: 'PUBLIC',
  })
  await page.goto(`/staff/exams/${empty.id}`)
  await page.getByRole('tab', { name: '统计分析', exact: true }).click()
  await expect(page.getByText('暂无已判完的最终作答样本。', { exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: '成绩指标' })).toContainText(/平均分\s*暂无数据/)
  await expect(page.getByRole('img', { name: '最终成绩分布图' })).toHaveCount(0)
  await fixture.context.close()
})

test('学生分析使用最终得分率与多标签错题计数，撤回或关闭回看隐藏细节', async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(120_000)
  const fixture = await resultsFixture(page, browser, { twoAttempts: true })
  const published = await publishFixture(page, fixture)
  const studentPage = await fixture.context.newPage()
  await studentPage.goto('/home')
  const entry = studentPage
    .getByRole('navigation', { name: '主导航' })
    .getByRole('link', { name: '学习分析', exact: true })
  await expect(entry).toBeVisible()
  await entry.click()
  await expect(
    studentPage.getByRole('img', { name: '最终得分率趋势图' }).locator('svg'),
  ).toBeVisible()
  await expect(studentPage.getByRole('img', { name: '题型得分率图' }).locator('svg')).toBeVisible()
  await expect(
    studentPage.getByRole('img', { name: '知识点错题分布图' }).locator('svg'),
  ).toBeVisible()
  await studentPage.getByText('查看趋势数据', { exact: true }).click()
  await expect(
    studentPage.getByRole('row', { name: new RegExp(`${fixture.exam.title}.*15.0.*100.0%`) }),
  ).toBeVisible()
  await studentPage.getByText('查看知识点数据', { exact: true }).click()
  await expect(studentPage.getByRole('row', { name: /函数.*3/ })).toBeVisible()
  await expect(
    studentPage.getByText('一题多标签可分别计入；数量按错误作答记录统计。', { exact: true }),
  ).toBeVisible()
  await captureResponsive(studentPage, testInfo, 'student-analytics')
  await apiWrite(page.request, `/staff/exams/${fixture.exam.id}/withdraw-results`, {
    version: published.version,
    reason: '复核分析来源成绩。',
  })
  await studentPage.getByRole('button', { name: '刷新分析', exact: true }).click()
  await expect(studentPage.getByText('暂无已公布的最终成绩。', { exact: true })).toBeVisible()
  await expect(studentPage.getByRole('img', { name: '最终得分率趋势图' })).toHaveCount(0)
  await expect(studentPage.getByRole('img', { name: '知识点错题分布图' })).toHaveCount(0)
  await fixture.context.close()
  const locked = await resultsFixture(page, browser, { allowReview: false })
  await publishFixture(page, locked)
  const lockedPage = await locked.context.newPage()
  await lockedPage.goto('/student/analytics')
  await expect(
    lockedPage.getByRole('img', { name: '最终得分率趋势图' }).locator('svg'),
  ).toBeVisible()
  await expect(lockedPage.getByText('暂无允许回看的题型数据。', { exact: true })).toBeVisible()
  await expect(lockedPage.getByText('暂无可见的知识点错题记录。', { exact: true })).toBeVisible()
  await expect(lockedPage.getByRole('img', { name: '题型得分率图' })).toHaveCount(0)
  await lockedPage.goto(`/student/results/${locked.exam.id}`)
  await expect(lockedPage.getByText(/本场未开放答卷回看/)).toBeVisible()
  await expect(lockedPage.getByRole('link', { name: '回看答卷', exact: true })).toHaveCount(0)
  await locked.context.close()
})
