import type { QuestionInput } from '../../api/questions'
import type { ContentFieldErrors } from '../contentValidation'

export function choiceAnswerError(
  question: Pick<QuestionInput, 'type' | 'options' | 'standard_answer'>,
): string {
  if (!['SINGLE_CHOICE', 'MULTIPLE_CHOICE'].includes(question.type)) return ''
  const answer = Array.isArray(question.standard_answer) ? question.standard_answer : []
  if (question.type === 'SINGLE_CHOICE' && answer.length !== 1) return '单选题请选择一个正确选项。'
  if (question.type === 'MULTIPLE_CHOICE' && answer.length < 2)
    return '多选题请至少选择两个正确选项。'
  if (
    new Set(answer).size !== answer.length ||
    answer.some((id) => !question.options.some((option) => option.id === id))
  )
    return '请选择有效且不重复的正确选项。'
  return ''
}

/** 题库与考试快照使用同一组内容约束，保持与 QuestionContent 契约一致。 */
export function questionErrors(question: QuestionInput): ContentFieldErrors {
  const errors: ContentFieldErrors = {}
  if (!question.subject.trim()) errors.subject = '请填写科目。'
  else if (Array.from(question.subject).length > 100) errors.subject = '科目最多填写 100 个字符。'
  if (question.knowledge_tags.length > 30) errors.knowledge_tags = '知识点最多填写 30 个。'
  else if (question.knowledge_tags.some((tag) => !tag.trim() || Array.from(tag).length > 100))
    errors.knowledge_tags = '每个知识点须填写 1—100 个字符。'
  if (!question.content.trim()) errors.content = '请填写题干。'
  else if (Array.from(question.content).length > 100000)
    errors.content = '题干最多填写 100000 个字符。'
  if (question.explanation && Array.from(question.explanation).length > 100000)
    errors.explanation = '解析最多填写 100000 个字符。'
  if (['SINGLE_CHOICE', 'MULTIPLE_CHOICE'].includes(question.type)) {
    if (question.options.length < 2 || question.options.length > 8)
      errors.standard_answer = '选择题需要 2—8 个选项。'
    question.options.forEach((option) => {
      if (!option.content.trim()) errors[`option.${option.id}`] = '请填写选项内容。'
      else if (Array.from(option.content).length > 20000)
        errors[`option.${option.id}`] = '每个选项最多填写 20000 个字符。'
    })
    const answerIssue = choiceAnswerError(question)
    if (answerIssue) errors.standard_answer = answerIssue
  }
  return errors
}
