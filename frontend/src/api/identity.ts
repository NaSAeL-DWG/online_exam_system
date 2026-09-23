import { request, requestResult, type ApiResult } from './client'
import { pageQuery, type PageQuery, type PageResult } from './pagination'
import type { User, UserRole, UserSummary, StudentApplication, StudentReview } from '../types'

export interface TeacherInput {
  teacher_no: string
  real_name: string
  email: string
  phone_number: string
  temporary_password: string
}

export interface AccountUpdate {
  login_name: string
  real_name: string
  status?: 'ACTIVATED' | 'DEACTIVATED'
}

export interface ApplicationInput {
  student_no: string
  real_name: string
  email: string
  phone_number: string
}

export const identityApi = {
  teachers(query: PageQuery): Promise<PageResult<UserSummary>> {
    return request(`/admin/teachers?${pageQuery(query, { status: 'ACTIVATED' })}`)
  },
  students(query: PageQuery): Promise<PageResult<UserSummary>> {
    return request(`/staff/students?${pageQuery(query, { status: 'ACTIVATED' })}`)
  },
  reviews(query: PageQuery): Promise<PageResult<StudentReview>> {
    return request(`/staff/reviews?${pageQuery(query)}`)
  },
  decideReview(
    id: string,
    decision: 'APPROVED' | 'REJECTED',
    reason?: string,
  ): Promise<{ application: StudentApplication }> {
    return request(`/staff/reviews/${id}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision, reason }),
    })
  },
  application(): Promise<{ application: StudentApplication }> {
    return request('/student/application')
  },
  resubmitApplication(input: ApplicationInput): Promise<{ application: StudentApplication }> {
    return request('/student/application', { method: 'PUT', body: JSON.stringify(input) })
  },
  accounts(query: PageQuery, role?: UserRole): Promise<PageResult<User>> {
    return request(`/admin/users?${pageQuery(query, { user_type: role })}`)
  },
  createTeacher(input: TeacherInput): Promise<{ user: User }> {
    return request('/admin/teachers', { method: 'POST', body: JSON.stringify(input) })
  },
  updateAccount(id: string, input: AccountUpdate): Promise<ApiResult<{ user: User }>> {
    return requestResult(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(input) })
  },
  resetPassword(id: string, temporaryPassword: string): Promise<ApiResult<void>> {
    return requestResult(`/admin/users/${id}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ temporary_password: temporaryPassword }),
    })
  },
}
