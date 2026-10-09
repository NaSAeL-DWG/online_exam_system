<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { NAlert, NButton, NModal } from 'naive-ui'
import { gradingApi, type StaffAttemptDetail } from '../../api/grading'
import { identityApi } from '../../api/identity'
import { ApiError, errorMessage, isWriteResultUnknown } from '../../api/client'
import { usePagedList } from '../../composables/usePagedList'
import ListPager from '../../components/ListPager.vue'
import type { UserSummary } from '../../types'
import { textError, useContentValidation, type ContentFieldErrors } from '../contentValidation'
const props = defineProps<{ attempt: StaffAttemptDetail }>()
const emit = defineEmits<{
  close: []
  saved: [attempt: StaffAttemptDetail]
  refreshed: [attempt: StaffAttemptDetail]
}>()
const candidates = usePagedList(identityApi.teachers)
const {
  items,
  page,
  total,
  query,
  loading,
  failure: candidateFailure,
  load,
  changePage,
} = candidates
const teacherId = ref('')
const selected = ref<UserSummary | null>(null)
const reason = ref('')
const saving = ref(false)
const failure = ref('')
const needsReload = ref(false)
const formRoot = ref<HTMLFormElement | null>(null)
const errorPrefix = useId()
const { errors, validate } = useContentValidation(() => {
  const errors: ContentFieldErrors = {}
  if (!teacherId.value) errors.teacher_id = '请选择阅卷教师。'
  const reasonIssue = textError(reason.value, '改派原因', 2000, true)
  if (reasonIssue) errors.reason = reasonIssue
  return errors
})
const options = computed(() => {
  const users = new Map(items.value.map((teacher) => [teacher.id, teacher]))
  if (selected.value) users.set(selected.value.id, selected.value)
  return [...users.values()]
})
function select(value: string): void {
  teacherId.value = value
  selected.value = options.value.find((teacher) => teacher.id === value) || null
}
async function save(): Promise<void> {
  if (saving.value || needsReload.value || !props.attempt.task || !validate(formRoot.value)) return
  saving.value = true
  failure.value = ''
  try {
    const updated = await gradingApi.reassign(props.attempt.task.id, {
      version: props.attempt.task.version,
      teacher_id: teacherId.value,
      reason: reason.value.trim(),
    })
    emit('saved', updated)
    emit('close')
  } catch (error) {
    failure.value = errorMessage(error)
    needsReload.value =
      isWriteResultUnknown(error) ||
      (error instanceof ApiError &&
        ['VERSION_CONFLICT', 'GRADING_TASK_STATE_INVALID'].includes(error.problem.code))
  } finally {
    saving.value = false
  }
}
async function reloadTask(): Promise<void> {
  saving.value = true
  try {
    emit('refreshed', await gradingApi.attempt(props.attempt.id))
    emit('close')
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    saving.value = false
  }
}
</script>
<template>
  <NModal
    :show="true"
    preset="card"
    title="改派阅卷任务"
    class="responsive-modal responsive-modal--wide"
    :mask-closable="false"
    :closable="!saving"
    :close-on-esc="!saving"
    @update:show="emit('close')"
  >
    <NAlert class="form-alert" type="info"
      >整份答卷改派给一位激活教师。已有题分与历史保留，原教师失去未完成首阅任务的评分权限。</NAlert
    >
    <NAlert v-if="failure" class="form-alert" type="error"
      >{{ failure }}
      <NButton v-if="needsReload" size="small" :loading="saving" @click="reloadTask"
        >重新读取任务</NButton
      ></NAlert
    >
    <form ref="formRoot" class="reassignment-form" novalidate @submit.prevent="save">
      <div class="toolbar">
        <input
          v-model="query"
          class="form-control toolbar-search"
          aria-label="搜索阅卷教师"
          placeholder="按姓名或工号搜索激活教师"
          :disabled="saving || needsReload"
          @keydown.enter.prevent="changePage(1)"
        /><NButton :loading="loading" :disabled="saving || needsReload" @click="changePage(1)"
          >查询阅卷教师</NButton
        >
      </div>
      <NAlert v-if="candidateFailure" type="error"
        >{{ candidateFailure }} <NButton size="small" @click="load">重试读取教师</NButton></NAlert
      >
      <label class="field"
        >选择阅卷教师<select
          :value="teacherId"
          aria-label="选择阅卷教师"
          required
          :aria-invalid="!!errors.teacher_id"
          :aria-describedby="errors.teacher_id ? `${errorPrefix}-teacher-error` : undefined"
          :disabled="loading || saving || needsReload"
          @change="select(($event.target as HTMLSelectElement).value)"
        >
          <option value="">请选择激活教师</option>
          <option v-for="teacher in options" :key="teacher.id" :value="teacher.id">
            {{ teacher.real_name }}（{{ teacher.login_name }}）
          </option></select
        ><span
          v-if="errors.teacher_id"
          :id="`${errorPrefix}-teacher-error`"
          class="field-error"
          role="alert"
          >{{ errors.teacher_id }}</span
        ></label
      >
      <ListPager
        label="阅卷教师候选"
        :page="page"
        :total="total"
        :page-size="20"
        :loading="loading || saving"
        @change="changePage"
      />
      <label class="field"
        >改派原因<textarea
          v-model="reason"
          aria-label="改派原因"
          required
          rows="3"
          maxlength="2000"
          :aria-invalid="!!errors.reason"
          :aria-describedby="errors.reason ? `${errorPrefix}-reason-error` : undefined"
          :disabled="saving || needsReload"
        />
        <span
          v-if="errors.reason"
          :id="`${errorPrefix}-reason-error`"
          class="field-error"
          role="alert"
          >{{ errors.reason }}</span
        >
      </label>
      <div class="editor-actions">
        <NButton :disabled="saving" @click="emit('close')">取消改派</NButton
        ><NButton type="primary" attr-type="submit" :loading="saving" :disabled="needsReload"
          >确认改派</NButton
        >
      </div>
    </form>
  </NModal>
</template>
<style scoped>
.field-error {
  color: #b42318;
  font-size: 12px;
}
.reassignment-form {
  display: grid;
  gap: 20px;
}
.toolbar {
  margin: 0;
}
</style>
