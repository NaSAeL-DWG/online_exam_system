<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { NButton } from 'naive-ui'
import type { StaffAttemptQuestion } from '../../api/grading'
import {
  numberError,
  textError,
  useContentValidation,
  type ContentFieldErrors,
} from '../contentValidation'
const props = defineProps<{ question: StaffAttemptQuestion; saving: boolean; disabled: boolean }>()
const emit = defineEmits<{
  save: [input: { score: string; comment: string | null; reason: string | null }]
  dirty: [value: boolean]
}>()
const score = ref(props.question.answer.score || '')
const comment = ref(props.question.answer.grader_comment || '')
const reason = ref('')
const requiresReason = computed(() => props.question.answer.score !== null)
const formRoot = ref<HTMLFormElement | null>(null)
const errorPrefix = useId()
const { errors, validate, resetValidation } = useContentValidation(() => {
  const errors: ContentFieldErrors = {}
  const scoreIssue = numberError(score.value, '评分分值', {
    minimum: 0,
    maximum: Number(props.question.score),
    maximumLabel: `${props.question.score} 分`,
    decimalPlaces: 1,
  })
  if (scoreIssue) errors.score = scoreIssue
  const commentIssue = textError(comment.value, '阅卷评语', 20000)
  if (commentIssue) errors.comment = commentIssue
  const reasonIssue = textError(reason.value, '改分原因', 2000, requiresReason.value)
  if (reasonIssue) errors.reason = reasonIssue
  return errors
})
watch(
  () => props.question.answer,
  (answer) => {
    score.value = answer.score || ''
    comment.value = answer.grader_comment || ''
    reason.value = ''
    resetValidation()
  },
)
watch([score, comment, reason, () => props.question.answer], () =>
  emit(
    'dirty',
    score.value !== (props.question.answer.score || '') ||
      comment.value !== (props.question.answer.grader_comment || '') ||
      !!reason.value,
  ),
)
function save(): void {
  if (props.disabled || props.saving || !validate(formRoot.value)) return
  emit('save', {
    score: score.value,
    comment: comment.value.trim() || null,
    reason: reason.value.trim() || null,
  })
}
</script>
<template>
  <form ref="formRoot" class="grade-form" novalidate @submit.prevent="save">
    <div class="grade-form-header">
      <h3>{{ requiresReason ? '更正本题评分' : '人工评分' }}</h3>
      <span>支持 0—{{ question.score }} 分，一位小数。</span>
    </div>
    <label class="field grade-score-field"
      >评分分值
      <div class="score-input">
        <input
          :value="score"
          class="form-control"
          aria-label="评分分值"
          type="number"
          min="0"
          :max="question.score"
          step="0.1"
          required
          :aria-invalid="!!errors.score"
          :aria-describedby="errors.score ? `${errorPrefix}-score-error` : undefined"
          :disabled="disabled || saving"
          @input="score = ($event.target as HTMLInputElement).value"
        /><span>/ {{ question.score }} 分</span>
      </div>
      <span
        v-if="errors.score"
        :id="`${errorPrefix}-score-error`"
        class="field-error"
        role="alert"
        >{{ errors.score }}</span
      ></label
    >
    <label class="field"
      >阅卷评语（可选）<textarea
        v-model="comment"
        aria-label="阅卷评语"
        rows="3"
        maxlength="20000"
        :aria-invalid="!!errors.comment"
        :aria-describedby="errors.comment ? `${errorPrefix}-comment-error` : undefined"
        :disabled="disabled || saving"
      />
      <span
        v-if="errors.comment"
        :id="`${errorPrefix}-comment-error`"
        class="field-error"
        role="alert"
        >{{ errors.comment }}</span
      >
    </label>
    <label v-if="requiresReason" class="field"
      >改分原因<textarea
        v-model="reason"
        aria-label="改分原因"
        rows="2"
        maxlength="2000"
        required
        :aria-invalid="!!errors.reason"
        :aria-describedby="errors.reason ? `${errorPrefix}-reason-error` : undefined"
        :disabled="disabled || saving"
      />
      <span
        v-if="errors.reason"
        :id="`${errorPrefix}-reason-error`"
        class="field-error"
        role="alert"
        >{{ errors.reason }}</span
      >
    </label>
    <div class="grade-actions">
      <NButton type="primary" attr-type="submit" :loading="saving" :disabled="disabled"
        >保存本题评分</NButton
      ><span>逐题保存；所有题判完后自动汇总本次总分。</span>
    </div>
  </form>
</template>
<style scoped>
.grade-form {
  display: grid;
  gap: 20px;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--color-border);
}
.field-error {
  color: #b42318;
  font-size: 12px;
}
.grade-form-header {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: baseline;
  flex-wrap: wrap;
}
h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 650;
}
.grade-form-header span,
.grade-actions span {
  color: var(--color-muted);
  font-size: 12px;
}
.score-input {
  display: flex;
  gap: 12px;
  align-items: center;
}
.score-input input {
  max-width: 140px;
  font-size: 19px;
  font-weight: 600;
}
.score-input span {
  color: var(--color-muted);
  font-size: 13px;
}
.grade-actions {
  display: flex;
  gap: 14px;
  align-items: center;
  flex-wrap: wrap;
}
</style>
