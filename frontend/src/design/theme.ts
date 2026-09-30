import type { GlobalThemeOverrides } from 'naive-ui'

// 组件主题与 CSS token 同步，避免在页面中覆盖 Naive UI 的内部类名。
export const appTheme: GlobalThemeOverrides = {
  common: {
    primaryColor: '#087f73',
    primaryColorHover: '#066b61',
    primaryColorPressed: '#05584f',
    primaryColorSuppl: '#087f73',
    infoColor: '#397e9b',
    successColor: '#287a55',
    warningColor: '#a86613',
    errorColor: '#bd4944',
    textColorBase: '#202b2b',
    textColor1: '#202b2b',
    textColor2: '#465450',
    textColor3: '#697674',
    borderColor: '#dce3df',
    bodyColor: '#f5f6f4',
    cardColor: '#ffffff',
    borderRadius: '6px',
    fontFamily: 'Inter, "PingFang SC", "Microsoft YaHei", sans-serif',
    fontSize: '14px',
    heightMedium: '38px',
    heightLarge: '44px',
  },
  Button: { fontWeight: '600' },
  Card: { borderRadius: '10px', titleFontSizeMedium: '17px', titleFontWeight: '650' },
  DataTable: { thColor: '#f5f7f5', tdColorHover: '#f4f8f6', thFontWeight: '600' },
  Input: { color: '#ffffff', colorFocus: '#ffffff' },
}
