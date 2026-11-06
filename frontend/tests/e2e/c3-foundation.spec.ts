import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/auth/csrf', (route) =>
    route.fulfill({ json: { csrf_token: 'foundation-test-csrf' } }),
  )
  await page.route('**/api/auth/refresh', (route) => route.fulfill({ status: 401, json: {} }))
  await page.route('**/api/auth/me', (route) => route.fulfill({ status: 401, json: {} }))
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: '账号登录', exact: true })).toBeVisible()
  await page.evaluate(async () => {
    // 通过 Vite 加载原组件，避免用模拟 DOM 掩盖实际键盘或焦点问题。
    const modulePath = '/tests/e2e/c3-foundation-harness.ts'
    const { mountFoundationHarness } = await import(modulePath)
    mountFoundationHarness()
  })
})

test('下拉真实焦点具有标签和展开语义，键盘选项与错误清除同步', async ({ page }) => {
  const control = page.getByRole('combobox', { name: '状态', exact: true })
  await expect(control).toHaveAttribute('id', 'state-focus')
  await expect(control).toHaveAttribute('aria-invalid', 'true')
  await expect(control).toHaveAttribute('aria-describedby', 'state-hint')
  await control.focus()
  await expect(control).toBeFocused()
  await page.keyboard.press('ArrowDown')
  const listbox = page.getByRole('listbox', { name: '状态', exact: true })
  await expect(listbox).toBeVisible()
  await expect(control).toHaveAttribute('aria-expanded', 'true')
  await expect(listbox.getByRole('option', { name: '全部状态', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await page.keyboard.press('ArrowDown')
  const activeOption = listbox.getByRole('option', { name: '进行中', exact: true })
  await expect(control).toHaveAttribute(
    'aria-activedescendant',
    (await activeOption.getAttribute('id'))!,
  )
  await page.keyboard.press('Enter')
  await expect(control).toHaveText('进行中')
  await expect(control).toHaveAttribute('aria-expanded', 'false')
  await expect(control).not.toHaveAttribute('aria-activedescendant')
  await expect(control).toBeFocused()
  await expect(listbox).toHaveCount(0)
  await page.keyboard.press('Tab')
  const search = page.getByRole('combobox', { name: '搜索状态', exact: true })
  await expect(search).toBeFocused()
  await expect(search).toHaveAttribute('id', 'search-focus')
  await search.fill('进行')
  await expect(page.getByRole('listbox', { name: '搜索状态' }).getByRole('option')).toHaveCount(1)
  await page.keyboard.press('Escape')
  await expect(search).toHaveAttribute('aria-expanded', 'false')
  await expect(search).toBeFocused()
  await page.getByRole('button', { name: '清除校验', exact: true }).click()
  await expect(control).not.toHaveAttribute('aria-invalid')
  await expect(control).not.toHaveAttribute('aria-describedby')
})

test('多选保留选中语义与键盘清除，禁用控件不能取得 Tab 焦点', async ({ page }) => {
  const control = page.getByRole('combobox', { name: '多选状态', exact: true })
  await control.focus()
  await page.keyboard.press('ArrowDown')
  const listbox = page.getByRole('listbox', { name: '多选状态', exact: true })
  await expect(listbox).toHaveAttribute('aria-multiselectable', 'true')
  await expect(listbox.getByRole('option', { name: '不可选择' })).toHaveAttribute(
    'aria-disabled',
    'true',
  )
  await listbox.getByRole('option', { name: '进行中', exact: true }).click()
  await expect(listbox.getByRole('option', { name: '进行中', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await page.keyboard.press('Escape')
  await control.focus()
  // 库只在悬停或展开时显示清除图标，使用键盘展开，避免依赖退场动画的短暂 DOM。
  await page.keyboard.press('ArrowDown')
  await expect(listbox).toBeVisible()
  await page.keyboard.press('Tab')
  const clear = page.getByRole('button', { name: '清除多选状态', exact: true })
  await expect(clear).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('selected-values')).toHaveText('[]')
  await expect(control).toBeFocused()
  const disabled = page.getByRole('combobox', { name: '禁用状态', exact: true })
  await expect(disabled).toHaveAttribute('aria-disabled', 'true')
  await expect(disabled).toHaveAttribute('tabindex', '-1')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: '清除校验', exact: true })).toBeFocused()
  await page.getByRole('button', { name: '切换禁用', exact: true }).click()
  await expect(disabled).toHaveAttribute('aria-disabled', 'false')
  await expect(disabled).toHaveAttribute('tabindex', '0')
})

test('搜索多选支持首次与再次 Tab 进入，显式和包裹标签可激活控件', async ({ page }) => {
  const state = page.getByRole('combobox', { name: '状态', exact: true })
  await page.getByText('状态标签', { exact: true }).click()
  await expect(state).toBeFocused()
  const before = page.getByRole('button', { name: '搜索多选之前', exact: true })
  const after = page.getByRole('button', { name: '搜索多选之后', exact: true })
  const control = page.getByRole('combobox', { name: '搜索多选状态', exact: true })
  await before.focus()
  await page.keyboard.press('Tab')
  await expect(control).toBeFocused()
  await expect(control).toHaveJSProperty('tagName', 'INPUT')
  await expect(control).toHaveAttribute('id', 'search-multiple-focus')
  await expect(page.locator('#search-multiple-focus')).toHaveCount(1)
  await control.fill('进行')
  await expect(page.getByRole('listbox', { name: '搜索多选状态' }).getByRole('option')).toHaveCount(
    1,
  )
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('searchable-values')).toHaveText('["active"]')
  await page.keyboard.press('Escape')
  await expect(control).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(after).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(control).toBeFocused()
  await expect(control).toHaveJSProperty('tagName', 'INPUT')
  await before.focus()
  await page.getByText('搜索多选标签', { exact: true }).click()
  await expect(control).toBeFocused()
})

test('C3 输入焦点和菜单阴影遵循主题，骨架支持减少动态效果和窄屏', async ({ page }) => {
  const native = page.getByRole('textbox', { name: '原生输入框', exact: true })
  await native.focus()
  await expect(native).toHaveCSS('border-color', 'rgb(33, 100, 206)')
  await expect(native).toHaveCSS('outline-style', 'none')
  expect(await native.evaluate((element) => getComputedStyle(element).boxShadow)).toContain('inset')
  await page.getByRole('textbox', { name: '主题输入框', exact: true }).focus()
  await expect(page.locator('.n-input').last()).toHaveCSS('box-shadow', 'none')
  await expect(page.locator('.n-input__state-border').last()).toHaveCSS(
    'border',
    '2px solid rgb(33, 100, 206)',
  )
  await page.getByRole('combobox', { name: '状态', exact: true }).click()
  const listbox = page.getByRole('listbox', { name: '状态', exact: true })
  await expect(listbox).toHaveCSS('border-color', 'rgb(166, 166, 166)')
  await expect(listbox).not.toHaveCSS('box-shadow', 'none')
  await page.keyboard.press('Escape')
  await expect(page.locator('.n-base-select-menu:visible')).toHaveCount(0)
  const line = page.locator('.skeleton-line').first()
  expect(
    await line.evaluate((element) => getComputedStyle(element, '::after').animationDuration),
  ).toBe('3.2s')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  expect(await line.evaluate((element) => getComputedStyle(element, '::after').animationName)).toBe(
    'none',
  )
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
})
