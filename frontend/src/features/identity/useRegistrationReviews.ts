import { onMounted, ref } from 'vue'
import { useMessage } from 'naive-ui'
import { errorMessage } from '../../api/client'
import { identityApi } from '../../api/identity'
import type { StudentReview } from '../../types'
import { useFormValidation } from '../../composables/useFormValidation'
import { textRule } from './formRules'

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
  const rejectFailure = ref('')
  const rejectValidation = useFormValidation(
    () => ({ reason: reason.value }),
    {
      reason: textRule('拒绝原因'),
    },
    'review',
  )
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
    rejectFailure.value = ''
    if (decision === 'REJECTED' && !rejectValidation.validate()) {
      rejectFailure.value = '请检查标出的填写内容'
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
      if (decision === 'REJECTED') {
        rejectValidation.applyServerError(error)
        rejectFailure.value = errorMessage(error)
      } else message.error(errorMessage(error))
    } finally {
      saving.value = false
    }
  }
  function openReject(row: StudentReview): void {
    rejectValidation.clear()
    rejectFailure.value = ''
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
    rejectValidation,
    rejectFailure,
    load,
    changePage,
    decide,
    openReject,
  }
}
