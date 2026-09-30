import { onMounted, ref, shallowRef } from 'vue'
import { errorMessage } from '../api/client'
import type { PageQuery, PageResult } from '../api/pagination'

/** 保留当前页数据，通过请求序号阻止旧响应覆盖新的筛选结果。 */
export function usePagedList<T>(
  fetchPage: (query: PageQuery) => Promise<PageResult<T>>,
  pageSize = 20,
) {
  const items = shallowRef<T[]>([])
  const page = ref(1)
  const total = ref(0)
  const query = ref('')
  const loading = ref(false)
  const failure = ref('')
  let requestVersion = 0

  async function load(): Promise<void> {
    const version = ++requestVersion
    loading.value = true
    failure.value = ''
    try {
      const result = await fetchPage({ page: page.value, page_size: pageSize, q: query.value })
      if (version !== requestVersion) return
      items.value = result.items
      total.value = result.total
    } catch (error) {
      if (version === requestVersion) failure.value = errorMessage(error)
    } finally {
      if (version === requestVersion) loading.value = false
    }
  }

  function changePage(value: number): void {
    page.value = value
    void load()
  }

  onMounted(load)
  return { items, page, total, query, loading, failure, pageSize, load, changePage }
}
