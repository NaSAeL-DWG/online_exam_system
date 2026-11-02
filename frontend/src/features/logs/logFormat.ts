import type { LogEntry } from '../../api/logs'

/** 页面按浏览器本地时区显示，下载仍保留服务端的统一格式。 */
export function displayLogLine(entry: LogEntry): string {
  const time = new Date(entry.timestamp)
  const pad = (value: number, length = 2) => String(value).padStart(length, '0')
  const date = `${time.getFullYear()}-${pad(time.getMonth() + 1)}-${pad(time.getDate())}`
  const clock = `${pad(time.getHours())}:${pad(time.getMinutes())}:${pad(time.getSeconds())}.${pad(time.getMilliseconds(), 3)}`
  return entry.formatted.replace(/^\S+/, `${date} ${clock}`)
}
