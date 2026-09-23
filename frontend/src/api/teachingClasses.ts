import { request } from './client'
import { pageQuery, type PageQuery, type PageResult } from './pagination'
import type { TeachingClass } from '../types'

export interface ClassInput {
  name: string
  description: string
  teacher_ids: string[]
}

export const teachingClassesApi = {
  list(query: PageQuery): Promise<PageResult<TeachingClass>> {
    return request(`/classes?${pageQuery(query)}`)
  },
  detail(id: string): Promise<{ class_info: TeachingClass }> {
    return request(`/classes/${id}`)
  },
  create(input: ClassInput): Promise<{ class_info: TeachingClass }> {
    return request('/classes', { method: 'POST', body: JSON.stringify(input) })
  },
  update(
    id: string,
    input: Partial<ClassInput> & { status?: 'ARCHIVED' },
  ): Promise<{ class_info: TeachingClass }> {
    return request(`/classes/${id}`, { method: 'PATCH', body: JSON.stringify(input) })
  },
  addStudent(id: string, studentId: string): Promise<{ class_info: TeachingClass }> {
    return request(`/classes/${id}/members/${studentId}`, {
      method: 'PUT',
      body: JSON.stringify({ role: 'STUDENT' }),
    })
  },
  removeStudent(id: string, studentId: string): Promise<void> {
    return request(`/classes/${id}/members/${studentId}`, { method: 'DELETE' })
  },
}
