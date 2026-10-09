import type { FieldRule } from '../../composables/useFormValidation'

export function textRule(
  label: string,
  minLength = 1,
  maxLength?: number,
  preserveWhitespace = false,
): FieldRule {
  return {
    label,
    required: true,
    minLength,
    maxLength,
    check(value) {
      const text = typeof value === 'string' ? value : ''
      if (!(preserveWhitespace ? text : text.trim())) return `请填写${label}`
      // 与 Python 字符计数一致，避免把非BMP字符误算成两个字符。
      const length = Array.from(text).length
      if (length < minLength) return `至少需要${minLength}个字符`
      if (maxLength !== undefined && length > maxLength) return `最多允许${maxLength}个字符`
      return ''
    },
  }
}

export const emailRule: FieldRule = {
  label: '邮箱',
  required: true,
  check(value) {
    if (typeof value !== 'string' || !value.trim()) return '请填写邮箱'
    // 前端只做常见格式初检，EmailStr 仍由后端作最终判定。
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim()) ? '' : '请输入有效的邮箱地址'
  },
}
export const profileRules = {
  real_name: textRule('姓名', 1, 100),
  student_no: textRule('学号', 1, 100),
  email: emailRule,
  phone_number: textRule('手机号', 5, 32),
}
// 密码按原始字符校验，不能隐式trim或增加后端没有的复杂度限制。
export const passwordRule = (label = '密码') => textRule(label, 10, 256, true)
export const credentialRule = (label = '当前密码') => textRule(label, 1, undefined, true)
export function confirmationRule(source: string, label = '确认密码'): FieldRule {
  return {
    label,
    required: true,
    dependsOn: [source],
    check(value, values) {
      if (typeof value !== 'string' || !value) return `请填写${label}`
      return value === values[source] ? '' : '两次输入的密码不一致'
    },
  }
}
