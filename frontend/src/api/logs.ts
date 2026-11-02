import { request, requestBlob } from './client'

export type LogView = 'runtime' | 'audit'
export type LogLevel = 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG'

export interface LogEntry {
  id: string
  cursor: string
  timestamp: string
  formatted: string
  level?: string
  module?: string
  task?: string
  message?: string
  correlation_id?: string | null
  actor_id?: string | null
  actor_name?: string | null
  action?: string
  entity_type?: string
  entity_id?: string
  summary?: string
}

export interface LogPage {
  items: LogEntry[]
  next_before: string | null
  latest_cursor: string | null
  has_more: boolean
}

export interface LogSettings {
  file_enabled: boolean
  runtime_limit: number
  retention_days: number | null
  file_max_bytes: number
  file_count: number
  debug_modules: { module: string; expires_at: string }[]
}

export const logsApi = {
  list: (view: LogView, query: URLSearchParams) => request<LogPage>(`/admin/logs/${view}?${query}`),
  settings: () => request<LogSettings>('/admin/logs/settings'),
  setFile: (enabled: boolean) =>
    request<LogSettings>('/admin/logs/settings', {
      method: 'PATCH',
      body: JSON.stringify({ file_enabled: enabled }),
    }),
  setDebug: (module: string, enabled: boolean) =>
    request<LogSettings>(`/admin/logs/debug/${encodeURIComponent(module)}`, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    }),
  download: (view: LogView, query: URLSearchParams) =>
    requestBlob(`/admin/logs/${view}/export?${query}`, { method: 'POST' }),
}
