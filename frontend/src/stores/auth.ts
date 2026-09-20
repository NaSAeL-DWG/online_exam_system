import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError, errorMessage, request } from '../api/client'
import type { StudentApplication, User } from '../types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const ready = ref(false)
  const restoreError = ref('')
  const authenticated = computed(() => user.value !== null)

  async function restore(): Promise<void> {
    restoreError.value = ''
    try {
      user.value = (await request<{ user: User }>('/auth/me')).user
    } catch (error) {
      user.value = null
      if (!(error instanceof ApiError && error.status === 401)) {
        restoreError.value = errorMessage(error)
      }
    } finally {
      ready.value = true
    }
  }

  async function login(loginName: string, password: string): Promise<User> {
    const body = await request<{ user: User }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ login_name: loginName, password }),
    })
    user.value = body.user
    ready.value = true
    restoreError.value = ''
    return body.user
  }

  async function register(payload: Record<string, string>): Promise<StudentApplication> {
    const body = await request<{ user: User; application: StudentApplication }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    return body.application
  }

  async function logout(): Promise<void> {
    try {
      await request<void>('/auth/logout', { method: 'POST' })
    } finally {
      user.value = null
    }
  }

  function clear(): void {
    user.value = null
    ready.value = true
  }
  return { user, ready, restoreError, authenticated, restore, login, register, logout, clear }
})
