export interface ApiProblem {
  code: string
  message: string
  fields?: Record<string, string | string[]>
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly problem: ApiProblem,
  ) {
    super(problem.message)
  }
}

const writeMethods = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])
let csrfToken = ''
let csrfPromise: Promise<string> | null = null
let refreshPromise: Promise<boolean> | null = null

function readCookie(name: string): string {
  const prefix = `${encodeURIComponent(name)}=`
  const item = document.cookie.split('; ').find((value) => value.startsWith(prefix))
  return item ? decodeURIComponent(item.slice(prefix.length)) : ''
}

async function parseProblem(response: Response): Promise<ApiProblem> {
  const fallback = response.status >= 500 ? '服务暂时不可用，请稍后重试' : '请求未能完成'
  try {
    const body = (await response.json()) as { detail?: ApiProblem | string }
    if (typeof body.detail === 'string') return { code: 'REQUEST_FAILED', message: body.detail }
    if (body.detail?.message) return body.detail
  } catch {
    // 非 JSON 响应统一转为用户可理解的错误。
  }
  return { code: 'REQUEST_FAILED', message: fallback }
}

async function ensureCsrf(): Promise<string> {
  // Cookie 可能被其他标签页刷新，始终以浏览器当前值为准。
  const cookieToken = readCookie('csrf_token')
  if (cookieToken) {
    csrfToken = cookieToken
    return cookieToken
  }
  if (csrfPromise) return csrfPromise
  csrfPromise = (async () => {
    const response = await fetch('/api/auth/csrf', { credentials: 'include' })
    if (!response.ok) throw new ApiError(response.status, await parseProblem(response))
    const body = (await response.json()) as { csrf_token: string }
    csrfToken = body.csrf_token
    return csrfToken
  })().finally(() => {
    csrfPromise = null
  })
  return csrfPromise
}

async function rawFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const method = (init.method ?? 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (writeMethods.has(method)) headers.set('X-CSRF-Token', await ensureCsrf())
  return fetch(`/api${path}`, { ...init, method, headers, credentials: 'include' })
}

async function attemptRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise
  refreshPromise = (async () => {
    const perform = async (): Promise<boolean> => {
      // 获得跨标签页锁后先确认其他标签页是否已完成轮换。
      const me = await rawFetch('/auth/me')
      if (me.ok) return true
      if (me.status !== 401) throw new ApiError(me.status, await parseProblem(me))
      const refreshed = await rawFetch('/auth/refresh', { method: 'POST' })
      if (refreshed.ok) return true
      if (refreshed.status !== 401)
        throw new ApiError(refreshed.status, await parseProblem(refreshed))
      return false
    }
    try {
      return 'locks' in navigator
        ? await navigator.locks.request('online-exam-auth-refresh', perform)
        : await perform()
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError(0, { code: 'NETWORK_ERROR', message: '认证服务暂时不可用，请稍后重试' })
    }
  })().finally(() => {
    refreshPromise = null
  })
  return refreshPromise
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await rawFetch(path, init)
    const isAuthOperation = path === '/auth/login' || path === '/auth/refresh'
    if (response.status === 401 && !isAuthOperation) {
      const refreshed = await attemptRefresh()
      if (refreshed) response = await rawFetch(path, init)
    }
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError(0, {
      code: 'NETWORK_ERROR',
      message: '无法连接服务器，请检查网络后重试',
    })
  }
  if (!response!.ok) {
    const problem = await parseProblem(response!)
    // 首次进入公开页面时 /me 返回 401 只代表匿名，不应抢走当前导航。
    const accessRevoked = response!.status === 403 && problem.code === 'ACCOUNT_DEACTIVATED'
    if ((response!.status === 401 && path !== '/auth/me') || accessRevoked) {
      window.dispatchEvent(new CustomEvent('auth:expired'))
    }
    throw new ApiError(response!.status, problem)
  }
  if (response!.status === 204) return undefined as T
  return (await response!.json()) as T
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : '发生未知错误，请重试'
}
