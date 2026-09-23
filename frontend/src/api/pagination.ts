export interface PageQuery {
  page: number
  page_size: number
  q?: string
}

export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export function pageQuery(
  query: PageQuery,
  filters: Record<string, string | undefined> = {},
): string {
  const params = new URLSearchParams({
    page: String(query.page),
    page_size: String(query.page_size),
  })
  if (query.q?.trim()) params.set('q', query.q.trim())
  for (const [name, value] of Object.entries(filters)) {
    if (value) params.set(name, value)
  }
  return params.toString()
}
