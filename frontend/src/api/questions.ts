import { request } from './client'
import { pageQuery, type PageQuery, type PageResult } from './pagination'

export type QuestionType = 'SINGLE_CHOICE' | 'MULTIPLE_CHOICE' | 'TRUE_FALSE' | 'SHORT_ANSWER'
export type Difficulty = 'EASY' | 'MEDIUM' | 'HARD'
export interface QuestionInput {
  type: QuestionType
  content: string
  options: { id: string; content: string }[]
  standard_answer: string[] | boolean | string | null
  explanation: string | null
  subject: string
  knowledge_tags: string[]
  difficulty: Difficulty
}
export interface Question extends QuestionInput {
  id: string
  creator_id: string
  status: 'ACTIVE' | 'CLOSED'
  version: number
  created_at: string
  updated_at: string
}
export const questionTypeLabels: Record<QuestionType, string> = {
  SINGLE_CHOICE: '单选题',
  MULTIPLE_CHOICE: '多选题',
  TRUE_FALSE: '判断题',
  SHORT_ANSWER: '简答题',
}
export const questionsApi = {
  upload(
    file: File,
  ): Promise<{
    id: string
    url: string
    media_type: string
    size_bytes: number
    original_name: string
  }> {
    const body = new FormData()
    body.append('file', file)
    return request('/staff/assets', { method: 'POST', body })
  },
  list(
    query: PageQuery,
    filters: Record<string, string | undefined> = {},
  ): Promise<PageResult<Question>> {
    return request(`/staff/questions?${pageQuery(query, filters)}`)
  },
  get(id: string): Promise<Question> {
    return request(`/staff/questions/${id}`)
  },
  create(input: QuestionInput): Promise<Question> {
    return request('/staff/questions', { method: 'POST', body: JSON.stringify(input) })
  },
  update(id: string, input: QuestionInput, version: number): Promise<Question> {
    return request(`/staff/questions/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ ...input, version }),
    })
  },
  close(id: string, version: number): Promise<Question> {
    return request(`/staff/questions/${id}/close`, {
      method: 'POST',
      body: JSON.stringify({ version }),
    })
  },
}
