import { computed, onMounted, ref } from 'vue'
import { ApiError, errorMessage } from '../../api/client'
import { examsApi, type Exam, type SnapshotQuestion } from '../../api/exams'
import type { Question, QuestionInput } from '../../api/questions'

export function displayShanghaiTime(value: string | null): string {
  if (!value) return ''
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
    .format(new Date(value))
    .replace(' ', 'T')
}

/** 所有分区共享同一份草稿；保存时提交完整配置与快照，避免只保存当前分区。 */
export function useExamDraft(examId: () => string) {
  const exam = ref<Exam | null>(null)
  const form = ref<Exam | null>(null)
  const failure = ref('')
  const success = ref('')
  const conflict = ref(false)
  const loading = ref(false)
  const saving = ref(false)
  const start = ref('')
  const end = ref('')
  const duration = ref<number | null>(null)
  const questionVisible = ref(false)
  const questionIndex = ref(0)
  const editingQuestion = ref<QuestionInput | null>(null)
  const uploading = ref(false)
  const isDraft = computed(() => exam.value?.status === 'DRAFT')
  const dirty = computed(
    () =>
      !!(
        form.value &&
        exam.value &&
        (JSON.stringify(form.value) !== JSON.stringify(exam.value) ||
          start.value !== displayShanghaiTime(exam.value.start_at) ||
          end.value !== displayShanghaiTime(exam.value.end_at) ||
          duration.value !==
            (exam.value.duration_seconds ? exam.value.duration_seconds / 60 : null))
      ),
  )
  const draftTotal = computed(() =>
    (
      (form.value?.questions ?? []).reduce(
        (sum, question) => sum + Math.round(Number(question.score || 0) * 10),
        0,
      ) / 10
    ).toFixed(1),
  )

  function assign(value: Exam): void {
    exam.value = value
    form.value = structuredClone(value)
    start.value = displayShanghaiTime(value.start_at)
    end.value = displayShanghaiTime(value.end_at)
    duration.value = value.duration_seconds ? value.duration_seconds / 60 : null
    conflict.value = false
  }
  async function load(): Promise<void> {
    loading.value = true
    failure.value = ''
    success.value = ''
    try {
      assign(await examsApi.get(examId()))
    } catch (error) {
      failure.value = errorMessage(error)
    } finally {
      loading.value = false
    }
  }
  function recordError(error: unknown): void {
    failure.value = errorMessage(error)
    conflict.value = error instanceof ApiError && error.problem.code === 'VERSION_CONFLICT'
  }
  async function save(): Promise<void> {
    if (!form.value || !exam.value || saving.value) return
    saving.value = true
    failure.value = ''
    success.value = ''
    try {
      const value = form.value
      assign(
        await examsApi.update(exam.value.id, {
          title: value.title,
          description: value.description,
          audience_type: value.audience_type,
          start_at: start.value ? `${start.value}:00+08:00` : null,
          end_at: end.value ? `${end.value}:00+08:00` : null,
          duration_seconds: duration.value ? Number(duration.value) * 60 : null,
          max_attempts: Number(value.max_attempts),
          allow_review: value.allow_review,
          shuffle_questions: value.shuffle_questions,
          shuffle_options: value.shuffle_options,
          multiple_choice_mode: value.multiple_choice_mode,
          pass_percentage: String(value.pass_percentage),
          grader_ids: value.grader_ids,
          version: exam.value.version,
          questions: value.questions.map((question) => ({
            ...question,
            score: String(question.score),
          })),
        }),
      )
      success.value = '考试草稿已保存'
    } catch (error) {
      recordError(error)
    } finally {
      saving.value = false
    }
  }
  async function transition(action: 'publish' | 'withdraw'): Promise<void> {
    if (!exam.value || saving.value) return
    saving.value = true
    failure.value = ''
    success.value = ''
    try {
      assign(await examsApi[action](exam.value.id, exam.value.version))
    } catch (error) {
      recordError(error)
    } finally {
      saving.value = false
    }
  }
  function move(index: number, direction: number): void {
    const questions = form.value!.questions
    const item = questions.splice(index, 1)[0]
    if (item) questions.splice(index + direction, 0, item)
  }
  function addQuestion(question: Question): void {
    const {
      id,
      creator_id: _creator,
      status: _status,
      version: _version,
      created_at: _created,
      updated_at: _updated,
      ...content
    } = question
    form.value!.questions.push({
      ...(JSON.parse(JSON.stringify(content)) as QuestionInput),
      source_question_id: id,
      score: '1.0',
    })
  }
  function editQuestion(index: number): void {
    questionIndex.value = index
    editingQuestion.value = JSON.parse(
      JSON.stringify(form.value!.questions[index]),
    ) as SnapshotQuestion
    questionVisible.value = true
  }
  function applyQuestion(): void {
    Object.assign(form.value!.questions[questionIndex.value]!, editingQuestion.value)
    questionVisible.value = false
  }
  onMounted(load)
  return {
    exam,
    form,
    failure,
    success,
    conflict,
    loading,
    saving,
    start,
    end,
    duration,
    questionVisible,
    editingQuestion,
    uploading,
    isDraft,
    dirty,
    draftTotal,
    load,
    save,
    transition,
    move,
    addQuestion,
    editQuestion,
    applyQuestion,
  }
}
