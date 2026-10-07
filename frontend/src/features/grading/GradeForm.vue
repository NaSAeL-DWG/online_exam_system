<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NButton } from 'naive-ui'
import type { StaffAttemptQuestion } from '../../api/grading'
const props = defineProps<{ question: StaffAttemptQuestion; saving: boolean; disabled: boolean }>()
const emit = defineEmits<{
  save: [input: { score: string; comment: string | null; reason: string | null }]
  dirty: [value: boolean]
}>()
const score = ref(props.question.answer.score || '')
const comment = ref(props.question.answer.grader_comment || '')
const reason = ref('')
const requiresReason = computed(() => props.question.answer.score !== null)
watch(
  () => props.question.answer,
  (answer) => {
    score.value = answer.score || ''
    comment.value = answer.grader_comment || ''
    reason.value = ''
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
  emit('save', {
    score: score.value,
    comment: comment.value.trim() || null,
    reason: reason.value.trim() || null,
  })
}
</script>
<template>
  <form class="grade-form" @submit.prevent="save">
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
          :disabled="disabled || saving"
          @input="score = ($event.target as HTMLInputElement).value"
        /><span>/ {{ question.score }} 分</span>
      </div></label
    >
    <label class="field"
      >阅卷评语（可选）<textarea
        v-model="comment"
        aria-label="阅卷评语"
        rows="3"
        maxlength="2000"
        :disabled="disabled || saving"
      />
    </label>
    <label v-if="requiresReason" class="field"
      >改分原因<textarea
        v-model="reason"
        aria-label="改分原因"
        rows="2"
        maxlength="2000"
        required
        :disabled="disabled || saving"
      />
    </label>
    <div class="grade-actions">
      <NButton
        type="primary"
        attr-type="submit"
        :loading="saving"
        :disabled="disabled || !score.trim() || (requiresReason && !reason.trim())"
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
