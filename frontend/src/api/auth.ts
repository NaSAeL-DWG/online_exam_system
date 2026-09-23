import { request, requestResult, type ApiResult } from './client'
import type { ApplicationInput } from './identity'
import type { StudentApplication, User } from '../types'

export interface RegistrationInput extends ApplicationInput {
  password: string
}

export const authApi = {
  me(): Promise<{ user: User }> {
    return request('/auth/me')
  },
  login(loginName: string, password: string): Promise<{ user: User }> {
    return request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ login_name: loginName, password }),
    })
  },
  register(input: RegistrationInput): Promise<{ user: User; application: StudentApplication }> {
    return request('/auth/register', { method: 'POST', body: JSON.stringify(input) })
  },
  logout(): Promise<void> {
    return request('/auth/logout', { method: 'POST' })
  },
  changePassword(currentPassword: string, newPassword: string): Promise<ApiResult<void>> {
    return requestResult('/auth/password', {
      method: 'PUT',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    })
  },
  changeContacts(input: {
    current_password: string
    email: string
    phone_number: string
  }): Promise<ApiResult<{ user: User }>> {
    return requestResult('/auth/contacts', { method: 'PUT', body: JSON.stringify(input) })
  },
}
