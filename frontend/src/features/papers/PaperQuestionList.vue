<script setup lang="ts">
import { ref, useId, watch } from 'vue'
import { NButton } from 'naive-ui'
import { questionTypeLabels } from '../../api/questions'
import SafeMarkdown from '../../components/SafeMarkdown.vue'
import StatusBadge from '../../components/ui/StatusBadge.vue'
import type { SelectedPaperQuestion } from './usePaperEditor'
import { scoreCollectionErrors, useContentValidation } from '../contentValidation'
const model = defineModel<SelectedPaperQuestion[]>({ required: true })
defineProps<{ disabled: boolean }>()
const emit = defineEmits<{ move: [index: number, direction: number] }>()
const listRoot = ref<HTMLElement | null>(null)
const errorPrefix = useId()
const {
  errors,
  validate: validateFields,
  resetValidation,
} = useContentValidation(() => scoreCollectionErrors(model.value.map((item) => item.score)))
function validate(focus = true): boolean {
  return validateFields(listRoot.value, focus)
}
watch(model, resetValidation)
defineExpose({ validate, resetValidation })
</script>

<template>
  <section
    ref="listRoot"
    data-testid="selected-questions"
    class="selected-questions"
    aria-label="已选题目"
  >
    <p
      v-if="errors.questions"
      :id="`${errorPrefix}-questions-error`"
      class="field-error"
      role="alert"
      tabindex="-1"
      aria-invalid="true"
    >
      {{ errors.questions }}
    </p>
    <p v-if="!model.length" class="empty-selection">从题库加入题目，再安排顺序与分值。</p>
    <article v-for="(item, index) in model" :key="item.question.id" class="selected-question">
      <div class="question-heading">
        <span class="question-number">{{ String(index + 1).padStart(2, '0') }}</span>
        <div>
          <strong>第 {{ index + 1 }} 题</strong>
          <p class="muted">
            {{ questionTypeLabels[item.question.type] }} · {{ item.question.subject }}
          </p>
        </div>
        <StatusBadge v-if="item.question.status === 'CLOSED'" label="来源题已关闭" tone="warning" />
      </div>
      <SafeMarkdown :content="item.question.content" />
      <div class="question-controls">
        <div class="score-control">
          <label class="score-field"
            >分值<input
              v-model="item.score"
              class="form-control"
              :aria-label="`第 ${index + 1} 题分值`"
              type="number"
              min="0.1"
              max="999999999.9"
              step="0.1"
              required
              :aria-invalid="!!errors[`score.${index}`] || !!errors.questions"
              :aria-describedby="
                errors[`score.${index}`]
                  ? `${errorPrefix}-${index}-error`
                  : errors.questions
                    ? `${errorPrefix}-questions-error`
                    : undefined
              "
              :disabled="disabled"
            /><span class="muted">分</span></label
          ><span
            v-if="errors[`score.${index}`]"
            :id="`${errorPrefix}-${index}-error`"
            class="field-error"
            role="alert"
            >{{ errors[`score.${index}`] }}</span
          >
        </div>
        <div class="order-actions">
          <NButton
            size="small"
            :aria-label="`上移第 ${index + 1} 题`"
            :disabled="index === 0 || disabled"
            @click="emit('move', index, -1)"
            >上移</NButton
          ><NButton
            size="small"
            :aria-label="`下移第 ${index + 1} 题`"
            :disabled="index === model.length - 1 || disabled"
            @click="emit('move', index, 1)"
            >下移</NButton
          ><NButton size="small" :disabled="disabled" @click="model.splice(index, 1)">移出</NButton>
        </div>
      </div>
    </article>
  </section>
</template>

<style scoped>
.selected-questions {
  display: grid;
  gap: 12px;
  max-height: 490px;
  overflow-y: auto;
  padding-right: 4px;
}
.score-control {
  display: grid;
  gap: 6px;
}
.field-error {
  color: #b42318;
  font-size: 12px;
}
.selected-question {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 16px;
}
.question-heading {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.question-heading p {
  margin: 3px 0 0;
  font-size: 12px;
}
.question-number {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 5px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 700;
}
.question-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 10px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
}
.score-field {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
}
.score-field input {
  width: 78px;
}
.order-actions {
  display: flex;
  gap: 6px;
}
.empty-selection {
  padding: 34px 16px;
  text-align: center;
  color: var(--color-muted);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-sm);
}
</style>
