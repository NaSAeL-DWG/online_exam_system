import { request } from './client'
import { pageQuery, type PageQuery, type PageResult } from './pagination'
import type { TeachingClass, UserSummary } from '../types'

export interface Participant {
  id: string
  user: UserSummary
  status: 'ASSIGNED' | 'CANCELLED'
  version: number
  assigned_at: string
  cancelled_at: string | null
  cancelled_reason: string | null
  used_attempts: number
  voided_attempts: number
}
export const examParticipantsApi = {
  classes(query: PageQuery): Promise<PageResult<TeachingClass>> {
    return request(`/classes/audience-options?${pageQuery(query)}`)
  },
  list(examId: string, query: PageQuery, status: string): Promise<PageResult<Participant>> {
    return request(`/staff/exams/${examId}/participants?${pageQuery(query, { status })}`)
  },
  add(
    examId: string,
    classIds: string[],
    studentIds: string[],
  ): Promise<{ added: number; existing: number; cancelled_user_ids: string[] }> {
    return request(`/staff/exams/${examId}/participants`, {
      method: 'POST',
      body: JSON.stringify({ class_ids: classIds, student_ids: studentIds }),
    })
  },
  change(
    examId: string,
    participant: Participant,
    action: 'cancel' | 'restore',
    reason: string,
  ): Promise<Participant> {
    return request(`/staff/exams/${examId}/participants/${participant.id}/${action}`, {
      method: 'POST',
      body: JSON.stringify({ version: participant.version, reason }),
    })
  },
}
