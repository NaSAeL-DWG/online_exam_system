import { request } from './client'
import { pageQuery, type PageQuery, type PageResult } from './pagination'
import type { UserSummary } from '../types'
import type { QuestionType } from './questions'

export type GradingStatus = 'PENDING' | 'GRADING' | 'GRADED'
export type GradingTaskStatus = 'UNASSIGNED' | 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'VOID'

export interface GradingTask {
  id: string
  attempt_id: string
  assigned_teacher: UserSummary | null
  status: GradingTaskStatus
  grading_revision: number
  first_review_completed_at: string | null
  completed_at: string | null
  assigned_at: string | null
  version: number
}

export interface GradingTaskSummary extends GradingTask {
  exam_id: string
  exam_title: string
  student: UserSummary
  attempt_no: number
  can_grade: boolean
  can_reassign: boolean
}

export interface GradingTaskQuery extends PageQuery {
  exam_id?: string
  status?: GradingTaskStatus
  assigned_teacher_id?: string
}

export interface StaffAttemptSummary {
  id: string
  exam_id: string
  exam_title: string
  student: UserSummary
  attempt_no: number
  status: 'IN_PROGRESS' | 'SUBMITTED' | 'VOID'
  submitted_at: string | null
  effective_submitted_at: string | null
  grading_status: GradingStatus
  grading_revision: number
  final_score: string | null
  graded_at: string | null
  task: GradingTask | null
}

export interface FinalResult {
  participant_id: string
  student: UserSummary
  attempt_id: string | null
  attempt_no: number | null
  grading_status: GradingStatus | null
  final_score: string | null
  submitted_at: string | null
}

export type AnswerData = string[] | boolean | string | null
export interface GradedAnswer {
  id: string
  answer_data: AnswerData
  version: number
  grading_status: GradingStatus
  grading_revision: number
  score: string | null
  is_correct: boolean | null
  grader_comment: string | null
  graded_by: string | null
  grading_method: 'AUTO' | 'MANUAL' | null
  graded_at: string | null
}
export interface StaffAttemptQuestion {
  id: string
  type: QuestionType
  content: string
  options: { id: string; content: string }[]
  standard_answer: AnswerData
  explanation: string | null
  score: string
  grading_revision: number
  answer: GradedAnswer
  can_grade: boolean
}
export interface StaffAttemptDetail extends StaffAttemptSummary {
  questions: StaffAttemptQuestion[]
  can_grade: boolean
  can_reassign: boolean
  results_published: boolean
}
export interface GradeInput {
  version: number
  grading_revision: number
  score: string
  comment: string | null
  reason: string | null
}
export interface GradingHistoryEntry {
  id: string
  answer_id: string
  grading_revision: number
  actor: UserSummary | null
  method: 'AUTO' | 'MANUAL'
  old_score: string | null
  new_score: string | null
  old_is_correct: boolean | null
  new_is_correct: boolean | null
  old_comment: string | null
  new_comment: string | null
  reason: string | null
  created_at: string
}

export const gradingStatusLabels: Record<GradingStatus, string> = {
  PENDING: '待判分',
  GRADING: '待人工阅卷',
  GRADED: '已判完',
}

export const taskStatusLabels: Record<GradingTaskStatus, string> = {
  UNASSIGNED: '待指派',
  PENDING: '待阅卷',
  IN_PROGRESS: '阅卷中',
  COMPLETED: '已完成',
  VOID: '已作废',
}

export const gradingApi = {
  attempt(id: string): Promise<StaffAttemptDetail> {
    return request(`/staff/attempts/${id}`)
  },
  grade(answerId: string, input: GradeInput): Promise<StaffAttemptDetail> {
    return request(`/staff/answers/${answerId}/grade`, {
      method: 'POST',
      body: JSON.stringify(input),
    })
  },
  history(answerId: string): Promise<{ items: GradingHistoryEntry[] }> {
    return request(`/staff/answers/${answerId}/history`)
  },
  reassign(
    taskId: string,
    input: { version: number; teacher_id: string; reason: string },
  ): Promise<StaffAttemptDetail> {
    return request(`/admin/grading-tasks/${taskId}/reassign`, {
      method: 'POST',
      body: JSON.stringify(input),
    })
  },
  attempts(examId: string, query: PageQuery): Promise<PageResult<StaffAttemptSummary>> {
    return request(`/staff/exams/${examId}/attempts?${pageQuery(query)}`)
  },
  finalResults(examId: string, query: PageQuery): Promise<PageResult<FinalResult>> {
    return request(`/staff/exams/${examId}/final-results?${pageQuery(query)}`)
  },
  refresh(examId: string): Promise<{ graded_attempts: number; assigned_tasks: number }> {
    return request(`/staff/exams/${examId}/grading/refresh`, { method: 'POST', body: '{}' })
  },
  tasks(query: GradingTaskQuery): Promise<PageResult<GradingTaskSummary>> {
    const search = new URLSearchParams(pageQuery(query))
    if (query.exam_id) search.set('exam_id', query.exam_id)
    if (query.status) search.set('status', query.status)
    if (query.assigned_teacher_id) search.set('assigned_teacher_id', query.assigned_teacher_id)
    return request(`/staff/grading-tasks?${search}`)
  },
}
