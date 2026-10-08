import { request } from './client'
import type { AudienceType, ExamStatus } from './exams'
import type { QuestionType } from './questions'

export interface QuestionRate {
  question_id: string
  order_no: number
  type: QuestionType
  subject: string
  content: string
  full_score: string
  sample_count: number
  score_sum: string
  score_rate: string | null
}
export interface TeacherAnalytics {
  exam_id: string
  title: string
  exam_status: ExamStatus
  audience_type: AudienceType
  total_score: string
  pass_percentage: string
  ended: boolean
  expected_count: number | null
  participated_count: number
  submitted_count: number
  absent_count: number | null
  participation_rate: string | null
  in_progress_count: number
  pending_grading_count: number
  graded_count: number
  attempts_count: number
  submitted_attempts_count: number
  grading_tasks_count: number
  pending_grading_tasks_count: number
  average_score: string | null
  highest_score: string | null
  lowest_score: string | null
  pass_rate: string | null
  score_distribution: { label: string; lower_rate: string; upper_rate: string; count: number }[]
  question_rates: QuestionRate[]
  notes: string[]
}
export const analyticsApi = {
  teacher(examId: string, signal?: AbortSignal): Promise<TeacherAnalytics> {
    return request(`/staff/exams/${examId}/analytics`, { signal, cache: 'no-store' })
  },
}
