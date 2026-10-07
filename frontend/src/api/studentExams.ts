import { request } from './client'
import { pageQuery, type PageQuery, type PageResult } from './pagination'
import type { AudienceType, ExamStatus } from './exams'
import type { QuestionType } from './questions'

export type AttemptStatus = 'IN_PROGRESS' | 'SUBMITTED' | 'VOID'
export type AnswerData = string[] | boolean | string | null
export interface StudentExam {
  id: string
  title: string
  description: string | null
  audience_type: AudienceType
  status: ExamStatus
  start_at: string | null
  end_at: string | null
  duration_seconds: number | null
  max_attempts: number
  total_score: string
  server_now: string
  participant_status: 'ASSIGNED' | 'CANCELLED' | null
  cancelled_reason: string | null
  used_attempts: number
  remaining_attempts: number
  current_attempt_id: string | null
  current_attempt_status: AttemptStatus | null
  can_start: boolean
  unavailable_reason: string | null
}
export interface StudentAnswer {
  id: string
  answer_data: AnswerData
  version: number
  answered_at: string | null
}
export interface AttemptQuestion {
  id: string
  type: QuestionType
  content: string
  options: { id: string; content: string }[]
  score: string
  display_order: number
  answer: StudentAnswer
}
export interface AttemptDetail {
  id: string
  exam_id: string
  exam_title: string
  attempt_no: number
  status: AttemptStatus
  started_at: string
  deadline_at: string
  submitted_at: string | null
  effective_submitted_at: string | null
  submission_type: 'MANUAL' | 'TIMEOUT' | null
  grading_status: 'PENDING'
  server_now: string
  version: number
  token_generation: number
  questions: AttemptQuestion[]
}
export interface AttemptActivation extends AttemptDetail {
  page_token: string
}
export interface PagePermission {
  page_token: string
  token_generation: number
}

export const studentExamsApi = {
  list(query: PageQuery): Promise<PageResult<StudentExam>> {
    return request(`/student/exams?${pageQuery(query)}`)
  },
  get(id: string): Promise<StudentExam> {
    return request(`/student/exams/${id}`)
  },
  start(id: string): Promise<AttemptDetail> {
    return request(`/student/exams/${id}/attempts`, { method: 'POST', body: '{}' })
  },
  attempt(id: string): Promise<AttemptDetail> {
    return request(`/student/attempts/${id}`)
  },
  activate(
    id: string,
    pageToken?: string,
    expectedGeneration?: number,
  ): Promise<AttemptActivation> {
    const input: { page_token?: string; expected_generation?: number } = {}
    if (pageToken) input.page_token = pageToken
    else if (expectedGeneration !== undefined) input.expected_generation = expectedGeneration
    return request(`/student/attempts/${id}/activate`, {
      method: 'POST',
      body: JSON.stringify(input),
    })
  },
  save(
    id: string,
    answerId: string,
    permission: PagePermission,
    version: number,
    value: AnswerData,
  ): Promise<StudentAnswer> {
    return request(`/student/attempts/${id}/answers/${answerId}`, {
      method: 'PUT',
      body: JSON.stringify({ ...permission, version, answer_data: value }),
    })
  },
  submit(id: string, permission: PagePermission, confirmed: boolean): Promise<AttemptDetail> {
    return request(`/student/attempts/${id}/submit`, {
      method: 'POST',
      body: JSON.stringify({ ...permission, confirm_unanswered: confirmed }),
    })
  },
}
