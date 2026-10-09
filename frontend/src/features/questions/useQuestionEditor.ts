import { computed, ref } from 'vue'
import { ApiError, errorMessage } from '../../api/client'
import { questionsApi, type Question, type QuestionInput } from '../../api/questions'
import { blankQuestion } from './questionDraft'

export function useQuestionEditor(onSaved: () => Promise<void>) {
  const visible = ref(false)
  const selected = ref<Question | null>(null)
  const form = ref<QuestionInput>(blankQuestion())
  const saving = ref(false)
  const uploading = ref(false)
  const failure = ref('')
  const conflict = ref(false)
  const baseline = ref('')
  const dirty = computed(() => visible.value && JSON.stringify(form.value) !== baseline.value)

  function create(): void {
    selected.value = null
    form.value = blankQuestion()
    baseline.value = JSON.stringify(form.value)
    failure.value = ''
    conflict.value = false
    visible.value = true
  }
  async function edit(row: Question): Promise<void> {
    failure.value = ''
    try {
      const question = await questionsApi.get(row.id)
      selected.value = question
      form.value = structuredClone(question)
      baseline.value = JSON.stringify(form.value)
      conflict.value = false
      visible.value = true
    } catch (error) {
      failure.value = errorMessage(error)
    }
  }
  async function persist(action: 'save' | 'close' = 'save'): Promise<void> {
    if (saving.value || uploading.value) return
    saving.value = true
    failure.value = ''
    try {
      if (action === 'close' && selected.value)
        await questionsApi.close(selected.value.id, selected.value.version)
      else if (selected.value)
        await questionsApi.update(selected.value.id, form.value, selected.value.version)
      else await questionsApi.create(form.value)
      visible.value = false
      await onSaved()
    } catch (error) {
      failure.value = errorMessage(error)
      conflict.value = error instanceof ApiError && error.problem.code === 'VERSION_CONFLICT'
    } finally {
      saving.value = false
    }
  }
  return {
    visible,
    selected,
    form,
    saving,
    uploading,
    failure,
    conflict,
    dirty,
    create,
    edit,
    persist,
  }
}
