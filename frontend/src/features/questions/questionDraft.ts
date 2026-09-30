import type { QuestionInput } from '../../api/questions'

export function blankQuestion(): QuestionInput {
  return {
    type: 'TRUE_FALSE',
    content: '',
    options: [],
    standard_answer: true,
    explanation: null,
    subject: '',
    knowledge_tags: [],
    difficulty: 'MEDIUM',
  }
}

/** 切换题型时重设评分依据，选项 ID 保持独立于展示顺序。 */
export function changeQuestionType(question: QuestionInput): void {
  if (['SINGLE_CHOICE', 'MULTIPLE_CHOICE'].includes(question.type)) {
    if (question.options.length < 2) {
      question.options = [
        { id: crypto.randomUUID(), content: '' },
        { id: crypto.randomUUID(), content: '' },
      ]
    }
    question.standard_answer = []
  } else {
    question.options = []
    question.standard_answer = question.type === 'TRUE_FALSE' ? true : null
  }
}

export const difficultyLabels = { EASY: '简单', MEDIUM: '中等', HARD: '困难' }

export function questionSummary(content: string): string {
  return content
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '[图片]')
    .replace(/[\n\r]+/g, ' ')
    .trim()
}
