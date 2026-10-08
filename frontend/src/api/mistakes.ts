import { request } from './client'
import { pageQuery, type PageQuery, type PageResult } from './pagination'
import type { QuestionType } from './questions'
import type { ReviewQuestion } from './results'

export interface MistakeSummary {
  answer_id: string
  attempt_id: string
  attempt_no: number
  exam_id: string
  exam_title: string
  submitted_at: string | null
  question_id: string
  type: QuestionType
  subject: string
  knowledge_tags: string[]
  content: string
  score: string
  full_score: string
  note: string | null
  mastered: boolean
}
export interface MistakeDetail extends MistakeSummary {
  question: ReviewQuestion
}
export interface MistakeFilters {
  subject?: string
  type?: QuestionType | ''
  knowledge_tag?: string
  mastered?: 'true' | 'false' | ''
  q?: string
}
export interface MistakeAnnotation {
  note: string | null
  mastered: boolean
}

export const mistakesApi = {
  list(
    query: PageQuery,
    filters: MistakeFilters,
    signal?: AbortSignal,
  ): Promise<PageResult<MistakeSummary>> {
    return request(
      `/student/mistakes?${pageQuery(query, { subject: filters.subject, type: filters.type, knowledge_tag: filters.knowledge_tag, mastered: filters.mastered })}`,
      { signal, cache: 'no-store' },
    )
  },
  detail(answerId: string, signal?: AbortSignal): Promise<MistakeDetail> {
    return request(`/student/mistakes/${answerId}`, { signal, cache: 'no-store' })
  },
  annotate(answerId: string, input: MistakeAnnotation): Promise<MistakeAnnotation> {
    return request(`/student/mistakes/${answerId}/annotation`, {
      method: 'PUT',
      body: JSON.stringify(input),
      cache: 'no-store',
    })
  },
}
