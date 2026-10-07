import { ref } from 'vue'
import { ApiError, errorMessage, isWriteResultUnknown } from '../../api/client'
import { gradingApi, type StaffAttemptDetail, type StaffAttemptQuestion } from '../../api/grading'

/** 整份答卷以服务器快照为准，评分成功后同时更新任务、权限与本次总分。 */
export function useGradingWorkspace(attemptId: () => string) {
  const attempt = ref<StaffAttemptDetail | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const failure = ref('')
  const success = ref('')
  const needsReload = ref(false)
  let requestVersion = 0

  async function load(): Promise<void> {
    if (saving.value) return
    const version = ++requestVersion
    loading.value = true
    failure.value = ''
    success.value = ''
    try {
      const result = await gradingApi.attempt(attemptId())
      if (version !== requestVersion) return
      attempt.value = result
      needsReload.value = false
    } catch (error) {
      if (version === requestVersion) failure.value = errorMessage(error)
    } finally {
      if (version === requestVersion) loading.value = false
    }
  }

  async function grade(
    question: StaffAttemptQuestion,
    input: { score: string; comment: string | null; reason: string | null },
  ): Promise<void> {
    if (saving.value || needsReload.value || !question.can_grade) return
    saving.value = true
    failure.value = ''
    success.value = ''
    try {
      const result = await gradingApi.grade(question.answer.id, {
        version: question.answer.version,
        grading_revision: question.grading_revision,
        ...input,
      })
      attempt.value = result
      success.value = '本题评分已保存。'
    } catch (error) {
      failure.value =
        error instanceof ApiError && error.problem.code === 'VERSION_CONFLICT'
          ? '评分已发生变化，当前输入已保留。请重新读取最新评分后再保存。'
          : errorMessage(error)
      // 冲突或交付不确定时保留表单，不用旧版本自动重复评分。
      needsReload.value =
        isWriteResultUnknown(error) ||
        (error instanceof ApiError &&
          ['VERSION_CONFLICT', 'GRADING_FORBIDDEN', 'RESULTS_WITHDRAW_REQUIRED'].includes(
            error.problem.code,
          ))
    } finally {
      saving.value = false
    }
  }

  return { attempt, loading, saving, failure, success, needsReload, load, grade }
}
