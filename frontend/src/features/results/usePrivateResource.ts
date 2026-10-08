import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { errorMessage } from '../../api/client'

/** 敏感结果仅留在当前页面；每次重读先清空，且过期响应不能恢复旧成绩。 */
export function usePrivateResource<T>(
  key: () => unknown,
  fetchData: (signal: AbortSignal) => Promise<T>,
) {
  const data = shallowRef<T | null>(null)
  const loading = ref(false)
  const failure = ref('')
  let generation = 0
  let controller: AbortController | null = null

  async function load(): Promise<void> {
    const current = ++generation
    controller?.abort()
    const active = new AbortController()
    controller = active
    data.value = null
    failure.value = ''
    loading.value = true
    try {
      const result = await fetchData(active.signal)
      if (current === generation && !active.signal.aborted) data.value = result
    } catch (error) {
      if (current === generation && !active.signal.aborted) failure.value = errorMessage(error)
    } finally {
      if (current === generation) loading.value = false
    }
  }
  function refreshVisible(): void {
    if (document.visibilityState === 'visible') void load()
  }
  watch(key, () => void load(), { immediate: true })
  onMounted(() => {
    window.addEventListener('focus', refreshVisible)
    document.addEventListener('visibilitychange', refreshVisible)
  })
  onBeforeUnmount(() => {
    generation += 1
    controller?.abort()
    data.value = null
    window.removeEventListener('focus', refreshVisible)
    document.removeEventListener('visibilitychange', refreshVisible)
  })
  return { data, loading, failure, load }
}
