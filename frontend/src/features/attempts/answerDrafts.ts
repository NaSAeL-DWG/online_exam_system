import type { AnswerData } from '../../api/studentExams'

export interface AnswerDraft {
  version: number
  value: AnswerData
  sent?: { version: number; value: AnswerData }
}
export function draftStorage(userId: string, examId: string, attemptId: string) {
  const key = `online-exam-draft:${userId}:${examId}:${attemptId}`
  let available = true
  function read(): Record<string, AnswerDraft> {
    try {
      return JSON.parse(localStorage.getItem(key) || '{}') as Record<string, AnswerDraft>
    } catch {
      return {}
    }
  }
  function write(value: Record<string, AnswerDraft>): boolean {
    try {
      localStorage.setItem(key, JSON.stringify(value))
      return available
    } catch {
      available = false
      return false
    }
  }
  function clear(): void {
    try {
      localStorage.removeItem(key)
    } catch {
      available = false
    }
  }
  return { read, write, clear }
}

/** false 代表合法判断答案；只将 null、空数组及空白简答认作空题。 */
export function isUnanswered(value: AnswerData): boolean {
  return (
    value === null ||
    (Array.isArray(value) && value.length === 0) ||
    (typeof value === 'string' && value.trim() === '')
  )
}
export function normalizedAnswer(value: AnswerData): AnswerData {
  return isUnanswered(value) ? null : value
}
export function sameAnswer(left: AnswerData, right: AnswerData): boolean {
  return JSON.stringify(normalizedAnswer(left)) === JSON.stringify(normalizedAnswer(right))
}
export function copyAnswer(value: AnswerData): AnswerData {
  return Array.isArray(value) ? [...value] : value
}
