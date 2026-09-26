import { request } from './client'
import { pageQuery, type PageQuery, type PageResult } from './pagination'
import type { QuestionInput } from './questions'
import type { UserSummary } from '../types'

export type AudienceType = 'PUBLIC' | 'RESTRICTED'
export type ExamStatus = 'DRAFT' | 'RELEASED' | 'RESULTS_PUBLISHED' | 'CANCELLED'
export interface SnapshotQuestion extends QuestionInput {
  id?: string
  source_question_id: string | null
  order_no?: number
  score: string
}
export interface ExamConfiguration {
  title: string
  description: string | null
  audience_type: AudienceType
  start_at: string | null
  end_at: string | null
  duration_seconds: number | null
  max_attempts: number
  allow_review: boolean
  shuffle_questions: boolean
  shuffle_options: boolean
  multiple_choice_mode: 'EXACT' | 'PARTIAL'
  pass_percentage: string
  grader_ids: string[]
}
export interface ExamSummary extends ExamConfiguration {
  id: string
  creator_id: string
  source_paper_id: string
  status: ExamStatus
  version: number
  total_score: string
}
export interface Exam extends ExamSummary {
  graders: UserSummary[]
  questions: SnapshotQuestion[]
  content_revision: number
  grading_revision: number
  warnings: string[]
}
export const examStatusLabels: Record<ExamStatus, string> = {
  DRAFT: '草稿',
  RELEASED: '已发布',
  RESULTS_PUBLISHED: '结果已公布',
  CANCELLED: '已取消',
}
export const examsApi = {
  list(query: PageQuery): Promise<PageResult<ExamSummary>> {
    return request(`/staff/exams?${pageQuery(query)}`)
  },
  get(id: string): Promise<Exam> {
    return request(`/staff/exams/${id}`)
  },
  create(input: {
    source_paper_id: string
    title: string
    description: string | null
    audience_type: AudienceType
  }): Promise<Exam> {
    return request('/staff/exams', { method: 'POST', body: JSON.stringify(input) })
  },
  update(
    id: string,
    input: ExamConfiguration & { version: number; questions: SnapshotQuestion[] },
  ): Promise<Exam> {
    return request(`/staff/exams/${id}`, { method: 'PUT', body: JSON.stringify(input) })
  },
  publish(id: string, version: number): Promise<Exam> {
    return request(`/staff/exams/${id}/publish`, {
      method: 'POST',
      body: JSON.stringify({ version }),
    })
  },
  withdraw(id: string, version: number): Promise<Exam> {
    return request(`/staff/exams/${id}/withdraw`, {
      method: 'POST',
      body: JSON.stringify({ version }),
    })
  },
}
