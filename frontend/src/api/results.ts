import { request } from './client'
import { pageQuery, type PageQuery, type PageResult } from './pagination'
import type { ExamStatus } from './exams'
import type { AnswerData, GradingStatus } from './grading'
import type { Difficulty, QuestionType } from './questions'

export type ResultState =
  'NOT_PUBLISHED' | 'CORRECTING' | 'PUBLISHED' | 'CANCELLED' | 'PARTICIPANT_CANCELLED'
export interface StudentResultSummary {
  exam_id: string
  title: string
  exam_status: ExamStatus
  result_state: ResultState
  participant_status: 'ACTIVE' | 'CANCELLED'
  end_at: string | null
  total_score: string
  allow_review: boolean
  can_review: boolean
  attempts_count: number
  final_attempt_id: string | null
  final_attempt_no: number | null
  grading_status: GradingStatus | null
  final_score: string | null
  submitted_at: string | null
}
export interface StudentResultAttempt {
  id: string
  attempt_no: number
  status: 'IN_PROGRESS' | 'SUBMITTED'
  started_at: string
  submitted_at: string | null
  grading_status: GradingStatus
  final_score: string | null
  can_review: boolean
}
export interface StudentResultDetail extends StudentResultSummary {
  attempts: StudentResultAttempt[]
}
export interface ReviewQuestion {
  id: string
  order_no: number
  display_order: number
  type: QuestionType
  content: string
  options: { id: string; content: string }[]
  standard_answer: AnswerData
  explanation: string | null
  subject: string
  knowledge_tags: string[]
  difficulty: Difficulty
  score: string
  answer: {
    id: string
    answer_data: AnswerData
    grading_status: GradingStatus
    score: string | null
    is_correct: boolean | null
    grader_comment: string | null
  }
}
export interface StudentReview {
  id: string
  exam_id: string
  exam_title: string
  attempt_no: number
  submitted_at: string | null
  total_score: string
  final_score: string | null
  questions: ReviewQuestion[]
}

export const resultStateLabels: Record<ResultState, string> = {
  NOT_PUBLISHED: '结果未公布',
  CORRECTING: '结果更正中',
  PUBLISHED: '结果已公布',
  CANCELLED: '考试已取消',
  PARTICIPANT_CANCELLED: '参考资格已撤销',
}

export const resultsApi = {
  list(query: PageQuery, signal?: AbortSignal): Promise<PageResult<StudentResultSummary>> {
    return request(`/student/results?${pageQuery(query)}`, { signal, cache: 'no-store' })
  },
  detail(examId: string, signal?: AbortSignal): Promise<StudentResultDetail> {
    return request(`/student/results/${examId}`, { signal, cache: 'no-store' })
  },
  review(attemptId: string, signal?: AbortSignal): Promise<StudentReview> {
    return request(`/student/attempts/${attemptId}/review`, { signal, cache: 'no-store' })
  },
}
