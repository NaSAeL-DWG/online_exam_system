<script setup lang="ts">
import { computed, ref } from 'vue'
import { NAlert, NButton, NModal, useDialog } from 'naive-ui'
import { examsApi, type Exam } from '../../api/exams'
import { ApiError, errorMessage, isWriteResultUnknown } from '../../api/client'
import type { QuestionInput } from '../../api/questions'
import SafeMarkdown from '../../components/SafeMarkdown.vue'
const props = defineProps<{ exam: Exam; questionIndex: number }>()
const emit = defineEmits<{ close: []; saved: [exam: Exam]; refreshed: [exam: Exam] }>()
const dialog = useDialog()
const question = computed(() => props.exam.questions[props.questionIndex]!)
const standard = ref<QuestionInput['standard_answer']>(
  Array.isArray(question.value.standard_answer)
    ? [...question.value.standard_answer]
    : question.value.standard_answer,
)
const explanation = ref(question.value.explanation || '')
const reason = ref('')
const saving = ref(false)
const failure = ref('')
const needsReload = ref(false)
function selectOption(id: string, checked: boolean): void {
  if (question.value.type === 'SINGLE_CHOICE') {
    standard.value = [id]
    return
  }
  const values = Array.isArray(standard.value) ? standard.value : []
  standard.value = checked ? [...values, id] : values.filter((value) => value !== id)
}
async function save(): Promise<void> {
  if (saving.value || needsReload.value || !reason.value.trim()) return
  saving.value = true
  failure.value = ''
  try {
    // 使用题目自身的依据版本；整场修订号不能替代单题版本检查。
    const updated = await examsApi.correctStandard(props.exam.id, question.value.id!, {
      version: props.exam.version,
      grading_revision: question.value.grading_revision!,
      standard_answer: standard.value,
      explanation: explanation.value.trim() || null,
      reason: reason.value.trim(),
    })
    emit('saved', updated)
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
function reload(): void {
  dialog.warning({
    title: '重新读取评分依据',
    content: '将放弃此表单尚未保存的依据修改，重新读取当前考试。',
    positiveText: '放弃修改并重新读取',
    negativeText: '保留当前输入',
    onPositiveClick: async () => {
      saving.value = true
      try {
        emit('refreshed', await examsApi.get(props.exam.id))
        emit('close')
      } catch (error) {
        failure.value = errorMessage(error)
      } finally {
        saving.value = false
      }
    },
  })
}
</script>
<template>
  <NModal
    :show="true"
    preset="card"
    title="更正评分依据"
    class="responsive-modal responsive-modal--wide"
    :mask-closable="false"
    :closable="!saving"
    :close-on-esc="!saving"
    @update:show="emit('close')"
  >
    <NAlert v-if="exam.status === 'RESULTS_PUBLISHED'" class="form-alert" type="warning"
      >本场结果已公布，请先退出此表单并撤回结果，再更正评分依据。</NAlert
    >
    <NAlert class="form-alert" type="warning"
      >仅更正本场考试的评分依据。受影响的有效答卷将重新判分，简答题会重开人工任务并保留首阅完成记录。</NAlert
    >
    <NAlert v-if="failure" class="form-alert" type="error"
      >{{ failure }}
      <NButton v-if="needsReload" size="small" @click="reload">重新读取评分依据</NButton></NAlert
    >
    <form class="correction-form" @submit.prevent="save">
      <div class="correction-question">
        <strong>第 {{ questionIndex + 1 }} 题</strong><SafeMarkdown :content="question.content" />
      </div>
      <div
        v-if="question.type.includes('CHOICE')"
        class="correction-options"
        role="group"
        aria-label="正确选项"
      >
        <label v-for="(option, index) in question.options" :key="option.id"
          ><input
            :type="question.type === 'SINGLE_CHOICE' ? 'radio' : 'checkbox'"
            name="corrected-standard"
            :aria-label="`更正正确选项 ${index + 1}`"
            :checked="Array.isArray(standard) && standard.includes(option.id)"
            :disabled="saving || needsReload"
            @change="selectOption(option.id, ($event.target as HTMLInputElement).checked)" /><span
            >{{ String.fromCharCode(65 + index) }}.</span
          ><SafeMarkdown :content="option.content"
        /></label>
      </div>
      <label v-else-if="question.type === 'TRUE_FALSE'" class="field"
        >判断标准答案<select
          v-model="standard"
          aria-label="判断标准答案"
          :disabled="saving || needsReload"
        >
          <option :value="true">真</option>
          <option :value="false">假</option>
        </select></label
      >
      <label v-else class="field"
        >简答评分依据（可选）<textarea
          :value="typeof standard === 'string' ? standard : ''"
          aria-label="简答评分依据"
          rows="5"
          :disabled="saving || needsReload"
          @input="standard = ($event.target as HTMLTextAreaElement).value || null"
        />
      </label>
      <label class="field"
        >解析与评分说明<textarea
          v-model="explanation"
          aria-label="更正解析与评分说明"
          rows="3"
          :disabled="saving || needsReload"
        />
      </label>
      <label class="field"
        >更正原因<textarea
          v-model="reason"
          aria-label="更正原因"
          rows="3"
          required
          maxlength="2000"
          :disabled="saving || needsReload"
        />
      </label>
      <div class="editor-actions">
        <NButton :disabled="saving" @click="emit('close')">取消更正</NButton
        ><NButton
          type="primary"
          attr-type="submit"
          :loading="saving"
          :disabled="!reason.trim() || needsReload || exam.status !== 'RELEASED'"
          >保存依据并重判</NButton
        >
      </div>
    </form>
  </NModal>
</template>
<style scoped>
.correction-form {
  display: grid;
  gap: 20px;
}
.correction-question {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--color-border);
}
.correction-question strong {
  display: block;
  margin-bottom: 12px;
}
.correction-options {
  display: grid;
  gap: 12px;
}
.correction-options label {
  display: flex;
  gap: 10px;
  align-items: baseline;
}
.correction-options input {
  accent-color: var(--color-primary);
}
</style>
