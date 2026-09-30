import { onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { errorMessage } from '../../api/client'
import { identityApi } from '../../api/identity'
import type { StudentReview } from '../../types'

export function useRegistrationReviews() {
  const items = ref<StudentReview[]>([])
  const loading = ref(false)
  const saving = ref(false)
  const failure = ref('')
  const page = ref(1)
  const pageSize = 20
  const total = ref(0)
  const query = ref('')
  let loadVersion = 0
  const selected = ref<StudentReview | null>(null)
  const rejectVisible = ref(false)
  const reason = ref('')
  const message = useMessage()

  async function load(): Promise<void> {
    const version = ++loadVersion
    loading.value = true
    failure.value = ''
    try {
      const result = await identityApi.reviews({
        page: page.value,
        page_size: pageSize,
        q: query.value,
      })
      if (version !== loadVersion) return
      items.value = result.items
      total.value = result.total
    } catch (error) {
      if (version !== loadVersion) return
      items.value = []
      failure.value = errorMessage(error)
    } finally {
      if (version === loadVersion) loading.value = false
    }
  }
  function changePage(value: number): void {
    page.value = value
    void load()
  }
  async function decide(row: StudentReview, decision: 'APPROVED' | 'REJECTED'): Promise<void> {
    if (saving.value) return
    if (decision === 'REJECTED' && !reason.value.trim()) {
      message.warning('请填写拒绝原因')
      return
    }
    saving.value = true
    try {
      await identityApi.decideReview(
        row.id,
        decision,
        decision === 'REJECTED' ? reason.value.trim() : undefined,
      )
      message.success(decision === 'APPROVED' ? '已通过学生申请' : '已拒绝学生申请')
      rejectVisible.value = false
      reason.value = ''
      await load()
    } catch (error) {
      message.error(errorMessage(error))
    } finally {
      saving.value = false
    }
  }
  function openReject(row: StudentReview): void {
    selected.value = row
    reason.value = ''
    rejectVisible.value = true
  }
  onMounted(load)
  return {
    items,
    loading,
    saving,
    failure,
    page,
    pageSize,
    total,
    query,
    selected,
    rejectVisible,
    reason,
    load,
    changePage,
    decide,
    openReject,
  }
}
