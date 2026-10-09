import { computed, nextTick, ref } from 'vue'

export type ContentFieldErrors = Record<string, string>

export function textError(
  value: string | null | undefined,
  label: string,
  maximum: number,
  required = false,
): string {
  if (required && !value?.trim()) return `请填写${label}。`
  if (value && Array.from(value).length > maximum) return `${label}最多填写 ${maximum} 个字符。`
  return ''
}

/** 字符串保留小数精度信息，允许后端同样接受的尾零和科学计数形式。 */
export function numberError(
  value: string | number | null,
  label: string,
  options: {
    minimum: number
    maximum: number
    decimalPlaces: number
    required?: boolean
    maximumLabel?: string
  },
): string {
  const text = value === null ? '' : String(value).trim()
  if (!text) return options.required === false ? '' : `请填写${label}。`
  const number = Number(text)
  if (!Number.isFinite(number)) return `${label}请输入有效数字。`
  if (number < options.minimum) return `${label}不能小于 ${options.minimum}。`
  if (number > options.maximum)
    return `${label}不能超过 ${options.maximumLabel ?? options.maximum}。`
  const [mantissa = '', exponent = '0'] = text.toLowerCase().split('e')
  const fraction = (mantissa.split('.')[1] ?? '').replace(/0+$/, '')
  if (fraction.length - Number(exponent) > options.decimalPlaces)
    return options.decimalPlaces === 0
      ? `${label}须为整数。`
      : `${label}最多保留 ${options.decimalPlaces} 位小数。`
  return ''
}

export function questionScoreError(value: string | number): string {
  return numberError(value, '题目分值', { minimum: 0.1, maximum: 999999999.9, decimalPlaces: 1 })
}

export function scoreCollectionErrors(scores: (string | number)[]): ContentFieldErrors {
  const errors: ContentFieldErrors = {}
  if (scores.length > 500) errors.questions = '最多加入 500 道题目。'
  scores.forEach((score, index) => {
    const issue = questionScoreError(score)
    if (issue) errors[`score.${index}`] = issue
  })
  if (
    !Object.keys(errors).length &&
    scores.reduce<number>((sum, score) => sum + Math.round(Number(score) * 10), 0) > 9999999999
  )
    errors.questions = '总分不能超过 999999999.9 分。'
  return errors
}

/** 校验失败后持续更新就近提示，提交时把焦点带到第一个错误字段。 */
export function useContentValidation(check: () => ContentFieldErrors) {
  const attempted = ref(false)
  const errors = computed(() => (attempted.value ? check() : {}))
  function validate(root: HTMLElement | null, focus = true): boolean {
    attempted.value = true
    const valid = Object.keys(check()).length === 0
    if (!valid && focus) {
      void nextTick(() => root?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus())
    }
    return valid
  }
  function resetValidation(): void {
    attempted.value = false
  }
  return { errors, validate, resetValidation }
}
