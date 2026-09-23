import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError, errorMessage } from '../api/client'
import { authApi, type RegistrationInput } from '../api/auth'
import type { StudentApplication, User } from '../types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const ready = ref(false)
  const restoreError = ref('')
  const notice = ref('')
  const authenticated = computed(() => user.value !== null)

  async function restore(): Promise<void> {
    restoreError.value = ''
    try {
      user.value = (await authApi.me()).user
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
    const body = await authApi.login(loginName, password)
    user.value = body.user
    ready.value = true
    restoreError.value = ''
    notice.value = ''
    return body.user
  }

  async function register(payload: RegistrationInput): Promise<StudentApplication> {
    const body = await authApi.register(payload)
    return body.application
  }

  async function logout(): Promise<void> {
    await authApi.logout()
    user.value = null
  }

  function clear(): void {
    user.value = null
    ready.value = true
  }
  return {
    user,
    ready,
    restoreError,
    notice,
    authenticated,
    restore,
    login,
    register,
    logout,
    clear,
  }
})
