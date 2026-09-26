import { request } from './client'
import { pageQuery, type PageQuery, type PageResult } from './pagination'
import type { Question } from './questions'

export interface PaperSummary {
  id: string
  creator_id: string
  title: string
  description: string | null
  status: 'ACTIVE' | 'ARCHIVED'
  version: number
  total_score: string
  question_count: number
}
export interface PaperQuestion {
  id: string
  question_id: string
  order_no: number
  score: string
  question: Question
}
export interface Paper extends PaperSummary {
  questions: PaperQuestion[]
}
export interface PaperInput {
  title: string
  description: string | null
  questions: { question_id: string; score: string }[]
}
export const papersApi = {
  list(query: PageQuery): Promise<PageResult<PaperSummary>> {
    return request(`/staff/papers?${pageQuery(query)}`)
  },
  get(id: string): Promise<Paper> {
    return request(`/staff/papers/${id}`)
  },
  create(input: PaperInput): Promise<Paper> {
    return request('/staff/papers', { method: 'POST', body: JSON.stringify(input) })
  },
  update(id: string, input: PaperInput, version: number): Promise<Paper> {
    return request(`/staff/papers/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ ...input, version }),
    })
  },
  archive(id: string, version: number): Promise<Paper> {
    return request(`/staff/papers/${id}/archive`, {
      method: 'POST',
      body: JSON.stringify({ version }),
    })
  },
}
