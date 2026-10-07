<script setup lang="ts">
import { ref } from 'vue'
import { NAlert, NButton, NModal } from 'naive-ui'
import { examsApi, type Exam } from '../../api/exams'
import { ApiError, errorMessage, isWriteResultUnknown } from '../../api/client'
const props = defineProps<{ exam: Exam }>()
const emit = defineEmits<{ close: []; saved: []; refresh: [] }>()
const reason = ref('')
const saving = ref(false)
const failure = ref('')
const needsReload = ref(false)
function refresh(): void {
  emit('refresh')
  emit('close')
}
async function save(): Promise<void> {
  if (saving.value || needsReload.value || !reason.value.trim()) return
  saving.value = true
  failure.value = ''
  try {
    await examsApi.withdrawResults(props.exam.id, props.exam.version, reason.value.trim())
    emit('saved')
    emit('close')
  } catch (error) {
    failure.value = errorMessage(error)
    needsReload.value =
      isWriteResultUnknown(error) ||
      (error instanceof ApiError && error.problem.code === 'VERSION_CONFLICT')
  } finally {
    saving.value = false
  }
}
</script>
<template>
  <NModal
    :show="true"
    preset="card"
    title="撤回已公布结果"
    class="responsive-modal"
    :mask-closable="false"
    :closable="!saving"
    :close-on-esc="!saving"
    @update:show="emit('close')"
  >
    <NAlert class="form-alert" type="warning"
      >撤回后学生将看到结果更正中的状态，后续查询隐藏成绩与答案。完成更正后需要重新公布。</NAlert
    >
    <NAlert v-if="failure" class="form-alert" type="error"
      >{{ failure }}
      <NButton v-if="needsReload" size="small" @click="refresh">核对最新考试状态</NButton></NAlert
    >
    <form class="withdraw-form" @submit.prevent="save">
      <label class="field"
        >撤回结果原因<textarea
          v-model="reason"
          aria-label="撤回结果原因"
          rows="3"
          maxlength="2000"
          required
          :disabled="saving || needsReload"
        />
      </label>
      <div class="editor-actions">
        <NButton :disabled="saving" @click="emit('close')">保留公布结果</NButton
        ><NButton
          type="primary"
          attr-type="submit"
          :loading="saving"
          :disabled="!reason.trim() || needsReload"
          >确认撤回结果</NButton
        >
      </div>
    </form>
  </NModal>
</template>
<style scoped>
.withdraw-form {
  display: grid;
  gap: 20px;
}
</style>
