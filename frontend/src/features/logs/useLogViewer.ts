import { nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ApiError, errorMessage } from '../../api/client'
import { logsApi, type LogEntry, type LogLevel, type LogView } from '../../api/logs'

const maximumEntries = 1000
const emptyFilters = () => ({
  start: '',
  end: '',
  level: 'INFO' as LogLevel,
  module: '',
  task: '',
  q: '',
  correlation_id: '',
  actor_id: '',
  action: '',
  entity_type: '',
  entity_id: '',
})

export function useLogViewer() {
  const view = ref<LogView>('runtime')
  const draft = reactive(emptyFilters())
  const entries = ref<LogEntry[]>([])
  const viewport = ref<HTMLElement | null>(null)
  const autoRefresh = ref(true)
  const autoScroll = ref(true)
  const following = ref(true)
  const loading = ref(false)
  const loadingHistory = ref(false)
  const failure = ref('')
  const filterFailure = ref('')
  const newCount = ref(0)
  const hasHistory = ref(false)
  const limited = ref(false)
  const updatedAt = ref('')
  const accessDenied = ref(false)
  let activeQuery = new URLSearchParams()
  let latestCursor: string | null = null
  let historyCursor: string | null = null
  let generation = 0
  let pollingGeneration: number | null = null
  let newerOmitted = false
  let timer: ReturnType<typeof setInterval> | undefined

  function query(): URLSearchParams {
    const result = new URLSearchParams()
    for (const key of ['start', 'end', 'q'] as const) {
      if (draft[key])
        result.set(key, key === 'q' ? draft[key].trim() : new Date(draft[key]).toISOString())
    }
    const keys =
      view.value === 'runtime'
        ? (['level', 'module', 'task', 'correlation_id'] as const)
        : (['actor_id', 'action', 'entity_type', 'entity_id'] as const)
    for (const key of keys) if (draft[key].trim()) result.set(key, draft[key].trim())
    return result
  }

  function scrollToBottom() {
    const element = viewport.value
    if (element) element.scrollTop = element.scrollHeight
  }

  async function reload() {
    if (accessDenied.value) return
    const current = ++generation
    entries.value = []
    latestCursor = null
    historyCursor = null
    pollingGeneration = null
    loadingHistory.value = false
    newCount.value = 0
    newerOmitted = false
    limited.value = false
    hasHistory.value = false
    failure.value = ''
    loading.value = true
    following.value = autoScroll.value
    try {
      const page = await logsApi.list(view.value, activeQuery)
      if (current !== generation) return
      entries.value = [...page.items].reverse()
      latestCursor = page.latest_cursor
      historyCursor = page.next_before
      hasHistory.value = page.has_more && !!page.next_before
      updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
      await nextTick()
      if (current === generation && following.value) scrollToBottom()
    } catch (error) {
      if (current === generation && !revokeAccess(error)) failure.value = errorMessage(error)
    } finally {
      if (current === generation) loading.value = false
    }
  }

  function applyFilters() {
    filterFailure.value = ''
    if (draft.start && draft.end && new Date(draft.start) > new Date(draft.end)) {
      filterFailure.value = '开始时间不能晚于结束时间'
      return
    }
    activeQuery = query()
    void reload()
  }

  function resetFilters() {
    Object.assign(draft, emptyFilters())
    applyFilters()
  }

  function changeView(value: LogView) {
    if (view.value === value) return
    view.value = value
    resetFilters()
  }

  // 轮询使用已应用的筛选快照；切换后旧成功和旧错误都不能改变新视图。
  async function refresh() {
    if (accessDenied.value || loading.value || pollingGeneration === generation) return
    const current = generation
    pollingGeneration = current
    const selectedView = view.value
    const selectedQuery = new URLSearchParams(activeQuery)
    try {
      let more = true
      let batches = 0
      while (more && batches < 10) {
        const firstPage = !latestCursor
        const params = new URLSearchParams(selectedQuery)
        if (latestCursor) params.set('after', latestCursor)
        const page = await logsApi.list(selectedView, params)
        if (current !== generation) return
        const seen = new Set(entries.value.map((entry) => entry.id))
        const incoming = [...page.items].reverse().filter((entry) => {
          if (seen.has(entry.id)) return false
          seen.add(entry.id)
          return true
        })
        if (page.latest_cursor) latestCursor = page.latest_cursor
        if (incoming.length) {
          const combined = [...entries.value, ...incoming]
          // 翻阅时保留当前历史，超过上限的新记录计数后可回到最新重新读取。
          if (combined.length > maximumEntries) {
            limited.value = true
            if (following.value) {
              entries.value = combined.slice(-maximumEntries)
              // 裁掉旧记录后，历史必须从当前最老项继续，不能沿用首次加载的游标。
              historyCursor = entries.value[0]?.cursor ?? null
              hasHistory.value = true
            } else {
              entries.value = combined.slice(0, maximumEntries)
              newerOmitted = true
            }
          } else entries.value = combined
          if (!following.value) newCount.value += incoming.length
          await nextTick()
          if (current !== generation) return
          if (following.value) scrollToBottom()
        }
        if (firstPage && incoming.length) {
          historyCursor = entries.value[0]?.cursor ?? null
          hasHistory.value = page.has_more && !!historyCursor
        }
        // 初空后的无 after 请求得到最新一页；has_more 在此表示更旧历史。
        more = !firstPage && page.has_more && !!page.latest_cursor && incoming.length > 0
        batches += 1
      }
      if (current === generation) {
        failure.value = ''
        updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
      }
    } catch (error) {
      if (current === generation && !revokeAccess(error)) failure.value = errorMessage(error)
    } finally {
      if (pollingGeneration === current) pollingGeneration = null
    }
  }

  async function loadOlder() {
    if (accessDenied.value || !historyCursor || loadingHistory.value || loading.value) return
    const current = generation
    loadingHistory.value = true
    following.value = false
    const element = viewport.value
    const anchor = element?.querySelector<HTMLElement>('.log-entry')
    const anchorId = anchor?.dataset.logId
    const anchorOffset = anchor?.getBoundingClientRect().top ?? 0
    const params = new URLSearchParams(activeQuery)
    params.set('before', historyCursor)
    try {
      const page = await logsApi.list(view.value, params)
      if (current !== generation) return
      const seen = new Set(entries.value.map((entry) => entry.id))
      const older = [...page.items].reverse().filter((entry) => !seen.has(entry.id))
      const combined = [...older, ...entries.value]
      if (combined.length > maximumEntries) {
        limited.value = true
        newerOmitted = true
      }
      entries.value = combined.slice(0, maximumEntries)
      historyCursor = page.next_before
      hasHistory.value = page.has_more && !!page.next_before
      await nextTick()
      if (current !== generation) return
      const restored = Array.from(element?.querySelectorAll<HTMLElement>('.log-entry') ?? []).find(
        (entry) => entry.dataset.logId === anchorId,
      )
      if (element && restored)
        element.scrollTop += restored.getBoundingClientRect().top - anchorOffset
    } catch (error) {
      if (current === generation && !revokeAccess(error)) failure.value = errorMessage(error)
    } finally {
      if (current === generation) loadingHistory.value = false
    }
  }

  function onScroll() {
    const element = viewport.value
    if (!element) return
    const atBottom = element.scrollHeight - element.scrollTop - element.clientHeight < 32
    following.value = autoScroll.value && atBottom
    if (atBottom && !newerOmitted) newCount.value = 0
  }

  function goLatest() {
    if (newerOmitted) void reload()
    else {
      newCount.value = 0
      following.value = autoScroll.value
      scrollToBottom()
    }
  }

  function clear() {
    generation += 1
    entries.value = []
    newCount.value = 0
    failure.value = ''
    latestCursor = null
    historyCursor = null
    loading.value = false
    loadingHistory.value = false
    hasHistory.value = false
    accessDenied.value = true
    autoRefresh.value = false
    autoScroll.value = false
    following.value = false
    clearInterval(timer)
  }

  function revokeAccess(error: unknown): boolean {
    if (!(error instanceof ApiError) || ![401, 403].includes(error.status)) return false
    clear()
    failure.value = '日志查看权限已失效，记录已清空。请重新登录后再查看。'
    return true
  }

  watch(autoScroll, (enabled) => {
    following.value = enabled
    if (enabled) goLatest()
  })
  onMounted(() => {
    applyFilters()
    timer = setInterval(() => {
      if (autoRefresh.value) void refresh()
    }, 3000)
    window.addEventListener('auth:expired', clear)
  })
  onBeforeUnmount(() => {
    clear()
    clearInterval(timer)
    window.removeEventListener('auth:expired', clear)
  })

  return {
    view,
    draft,
    entries,
    viewport,
    autoRefresh,
    autoScroll,
    following,
    loading,
    loadingHistory,
    failure,
    filterFailure,
    newCount,
    hasHistory,
    limited,
    updatedAt,
    accessDenied,
    changeView,
    applyFilters,
    resetFilters,
    refresh,
    reload,
    loadOlder,
    onScroll,
    goLatest,
    revokeAccess,
    exportQuery: () => new URLSearchParams(activeQuery),
  }
}
