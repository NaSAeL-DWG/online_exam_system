import { computed, ref } from 'vue'
import { ApiError, errorMessage } from '../../api/client'
import { papersApi, type Paper } from '../../api/papers'
import type { Question } from '../../api/questions'

export interface SelectedPaperQuestion {
  question: Question
  score: string
}

export function usePaperEditor(onSaved: () => Promise<void>) {
  const visible = ref(false)
  const selected = ref<Paper | null>(null)
  const title = ref('')
  const description = ref('')
  const questions = ref<SelectedPaperQuestion[]>([])
  const saving = ref(false)
  const failure = ref('')
  const conflict = ref(false)
  const baseline = ref('')
  const draftContent = computed(() =>
    JSON.stringify({
      title: title.value,
      description: description.value,
      questions: questions.value.map((item) => ({ id: item.question.id, score: item.score })),
    }),
  )
  const dirty = computed(() => visible.value && draftContent.value !== baseline.value)
  const archived = computed(() => selected.value?.status === 'ARCHIVED')
  // 以十分为整数累计，避免 0.1 + 0.2 的浮点显示误差；传输仍使用分数字符串。
  const draftTotal = computed(() =>
    (
      questions.value.reduce((sum, item) => sum + Math.round(Number(item.score || 0) * 10), 0) / 10
    ).toFixed(1),
  )

  function create(): void {
    selected.value = null
    title.value = ''
    description.value = ''
    questions.value = []
    baseline.value = draftContent.value
    failure.value = ''
    conflict.value = false
    visible.value = true
  }

  async function edit(id: string): Promise<void> {
    failure.value = ''
    try {
      const paper = await papersApi.get(id)
      selected.value = paper
      title.value = paper.title
      description.value = paper.description ?? ''
      questions.value = paper.questions.map((item) => ({
        question: item.question,
        score: item.score,
      }))
      baseline.value = draftContent.value
      conflict.value = false
      visible.value = true
    } catch (error) {
      failure.value = errorMessage(error)
    }
  }

  function move(index: number, direction: number): void {
    const item = questions.value.splice(index, 1)[0]
    if (item) questions.value.splice(index + direction, 0, item)
  }

  async function persist(action: 'save' | 'archive'): Promise<void> {
    if (saving.value) return
    saving.value = true
    failure.value = ''
    try {
      if (action === 'archive' && selected.value) {
        await papersApi.archive(selected.value.id, selected.value.version)
      } else {
        const input = {
          title: title.value,
          description: description.value || null,
          questions: questions.value.map((item) => ({
            question_id: item.question.id,
            score: String(item.score),
          })),
        }
        if (selected.value) await papersApi.update(selected.value.id, input, selected.value.version)
        else await papersApi.create(input)
      }
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
    title,
    description,
    questions,
    saving,
    failure,
    conflict,
    dirty,
    archived,
    draftTotal,
    create,
    edit,
    move,
    persist,
  }
}
