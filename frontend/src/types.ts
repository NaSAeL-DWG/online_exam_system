export type UserRole = 'STUDENT' | 'TEACHER' | 'ADMIN'
export type UserStatus = 'WAITING_ACTIVATE' | 'ACTIVATED' | 'DEACTIVATED'
export type ApplicationStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

export interface User {
  id: string
  login_name: string
  real_name: string
  email: string
  phone_number: string
  user_type: UserRole
  status: UserStatus
  must_change_password: boolean
  created_at: string
}

export interface UserSummary {
  id: string
  login_name: string
  real_name: string
  email?: string
  phone_number?: string
  status: UserStatus
  user_type?: UserRole
}

export interface StudentApplication {
  id: string
  status: ApplicationStatus
  reason: string | null
  submitted_profile: { student_no: string; real_name: string; email: string; phone_number: string }
  submitted_at: string
  reviewed_at: string | null
  reviewer_id: string | null
}

export interface StudentReview extends StudentApplication {
  user: UserSummary
}

export interface TeachingClass {
  id: string
  name: string
  description: string | null
  status: 'ACTIVE' | 'ARCHIVED'
  teachers: UserSummary[]
  students?: UserSummary[]
  student_count: number
  created_at: string
  updated_at: string
}
