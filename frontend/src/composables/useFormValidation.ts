import { nextTick, reactive, watch } from 'vue'
import { ApiError } from '../api/client'
import { normalizeFieldErrors } from '../api/fieldProblems'

export interface FieldRule {
  label: string
  check(value: unknown, values: Record<string, unknown>): string
  required?: boolean
  minLength?: number
  maxLength?: number
  dependsOn?: string[]
}

export function useFormValidation(
  values: () => Record<string, unknown>,
  rules: Record<string, FieldRule>,
  prefix: string,
) {
  const errors = reactive<Record<string, string>>({})
  let submitted = false
  const errorId = (field: string) => `${prefix}-${field}-error`
  function inputProps(field: string, label = rules[field]?.label) {
    return {
      id: `${prefix}-${field}`,
      'aria-label': label,
      'aria-required': rules[field]?.required ? true : undefined,
      'aria-invalid': Boolean(errors[field]),
      'aria-describedby': errors[field] ? errorId(field) : undefined,
    }
  }
  async function focusFirst(): Promise<void> {
    await nextTick()
    const first = Object.keys(rules).find((field) => errors[field])
    if (first) document.getElementById(`${prefix}-${first}`)?.focus()
  }
  function validate(): boolean {
    submitted = true
    const current = values()
    for (const [field, rule] of Object.entries(rules))
      errors[field] = rule.check(current[field], current)
    const valid = !Object.values(errors).some(Boolean)
    if (!valid) void focusFirst()
    return valid
  }
  function applyServerError(error: unknown): void {
    if (!(error instanceof ApiError)) return
    for (const [field, reason] of Object.entries(normalizeFieldErrors(error.problem.fields))) {
      if (field in rules) errors[field] = reason
    }
    void focusFirst()
  }
  function clear(): void {
    for (const field of Object.keys(errors)) delete errors[field]
    submitted = false
  }
  watch(
    () => ({ ...values() }),
    (current, previous) => {
      for (const [field, rule] of Object.entries(rules)) {
        const changed =
          current[field] !== previous[field] ||
          rule.dependsOn?.some((dependency) => current[dependency] !== previous[dependency])
        if (changed && (submitted || errors[field]))
          errors[field] = rule.check(current[field], current)
      }
    },
  )
  return { errors, errorId, inputProps, validate, applyServerError, clear }
}

export type FormValidation = ReturnType<typeof useFormValidation>
