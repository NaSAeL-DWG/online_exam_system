import { expect, type Locator, type Page } from '@playwright/test'

/** 按可见选项操作统一下拉框，覆盖真实弹层与键盘焦点。 */
export async function selectNaiveOption(
  page: Page,
  control: Locator,
  optionLabel: string,
): Promise<void> {
  await control.click()
  const option = page.getByRole('option', { name: optionLabel, exact: true })
  await expect(option).toBeVisible()
  await option.click()
}
