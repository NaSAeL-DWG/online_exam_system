<script setup lang="ts">
import { NButton } from 'naive-ui'
import SafeMarkdown from '../../components/SafeMarkdown.vue'
import StatusBadge from '../../components/ui/StatusBadge.vue'
import { questionTypeLabels } from '../../api/questions'
import type { AnswerData } from '../../api/studentExams'
import type { AnswerRow, SaveState } from './useAttemptWorkspace'

const props = defineProps<{ row: AnswerRow; number: number; disabled: boolean }>()
const emit = defineEmits<{ change: [value: AnswerData]; save: []; mark: [] }>()
const saveLabels: Record<SaveState, string> = {
  saved: '已保存',
  unsaved: '尚未上传',
  saving: '保存中…',
  failed: '保存失败',
  conflict: '版本冲突',
}
function multiple(optionId: string, checked: boolean): void {
  const selected = Array.isArray(props.row.value) ? props.row.value : []
  emit('change', checked ? [...selected, optionId] : selected.filter((id) => id !== optionId))
}
</script>

<template>
  <section class="answer-question" :aria-label="`第 ${number} 题作答`">
    <header class="question-heading">
      <div>
        <h2>第 {{ number }} 题</h2>
        <StatusBadge :label="questionTypeLabels[row.question.type]" /><span class="question-score"
          >{{ row.question.score }} 分</span
        >
      </div>
      <button
        class="mark-button"
        type="button"
        :aria-pressed="row.marked"
        :disabled="disabled"
        @click="emit('mark')"
      >
        {{ row.marked ? '★ 已标记待检查' : '☆ 标记待检查' }}
      </button>
    </header>
    <SafeMarkdown class="question-content" :content="row.question.content" />
    <fieldset
      v-if="row.question.type === 'SINGLE_CHOICE' || row.question.type === 'MULTIPLE_CHOICE'"
      class="answer-options"
      :disabled="disabled"
    >
      <legend class="sr-only">
        {{ row.question.type === 'SINGLE_CHOICE' ? '选择一个答案' : '选择所有符合的答案' }}
      </legend>
      <label
        v-for="(option, index) in row.question.options"
        :key="option.id"
        class="answer-option"
        :class="{ selected: Array.isArray(row.value) && row.value.includes(option.id) }"
      >
        <input
          v-if="row.question.type === 'SINGLE_CHOICE'"
          type="radio"
          :name="row.question.id"
          :aria-label="`${String.fromCharCode(65 + index)}. ${option.content}`"
          :checked="Array.isArray(row.value) && row.value.includes(option.id)"
          @change="emit('change', [option.id])"
        />
        <input
          v-else
          type="checkbox"
          :aria-label="`${String.fromCharCode(65 + index)}. ${option.content}`"
          :checked="Array.isArray(row.value) && row.value.includes(option.id)"
          @change="multiple(option.id, ($event.target as HTMLInputElement).checked)"
        />
        <span class="option-letter">{{ String.fromCharCode(65 + index) }}.</span
        ><SafeMarkdown :content="option.content" />
      </label>
    </fieldset>
    <fieldset
      v-else-if="row.question.type === 'TRUE_FALSE'"
      class="answer-options"
      :disabled="disabled"
    >
      <legend class="sr-only">判断对错</legend>
      <label
        v-for="value in [true, false]"
        :key="String(value)"
        class="answer-option"
        :class="{ selected: row.value === value }"
        ><input
          type="radio"
          :name="row.question.id"
          :aria-label="value ? '正确' : '错误'"
          :checked="row.value === value"
          @change="emit('change', value)"
        /><span>{{ value ? '正确' : '错误' }}</span></label
      >
    </fieldset>
    <label v-else class="field short-answer-label"
      >简答答案<textarea
        :value="typeof row.value === 'string' ? row.value : ''"
        aria-label="简答答案"
        rows="9"
        maxlength="20000"
        :disabled="disabled"
        placeholder="请输入纯文本答案"
        @input="emit('change', ($event.target as HTMLTextAreaElement).value)"
      /><span class="muted">停止输入后自动保存，也可点击保存本题。</span></label
    >
    <footer class="question-save">
      <div>
        <span role="status" aria-label="本题保存状态" :class="`save-${row.state}`">{{
          saveLabels[row.state]
        }}</span>
        <p v-if="row.error" class="save-error" role="alert">{{ row.error }}</p>
      </div>
      <div class="question-save-actions">
        <NButton
          v-if="row.value !== null"
          size="small"
          :disabled="disabled"
          @click="emit('change', null)"
          >清空答案</NButton
        ><NButton
          size="small"
          :disabled="disabled || row.state === 'conflict'"
          :loading="row.state === 'saving'"
          @click="emit('save')"
          >{{ row.state === 'failed' ? '重试保存本题' : '保存本题' }}</NButton
        >
      </div>
    </footer>
  </section>
</template>

<style scoped>
.answer-question {
  min-width: 0;
}
.question-heading,
.question-heading > div {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.question-heading {
  justify-content: space-between;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--color-border);
}
h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 650;
}
.question-score {
  color: var(--color-muted);
  font-size: 13px;
}
.mark-button {
  border: 0;
  background: transparent;
  color: var(--color-muted);
  font-size: 13px;
  padding: 5px 0;
}
.mark-button[aria-pressed='true'] {
  color: var(--color-primary);
  font-weight: 600;
}
.question-content {
  padding: 24px 0;
}
.answer-options {
  border: 0;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 12px;
  min-width: 0;
}
.answer-option {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 15px 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  line-height: 1.8;
  cursor: pointer;
}
.answer-option.selected {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
}
.answer-option input {
  margin: 6px 0 0;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  accent-color: var(--color-primary);
}
.option-letter {
  color: var(--color-muted);
}
.short-answer-label > span {
  font-size: 12px;
}
.question-save {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding-top: 24px;
  margin-top: 24px;
  border-top: 1px solid var(--color-border);
  font-size: 13px;
}
.question-save-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex-shrink: 0;
}
.save-saved {
  color: var(--color-primary);
}
.save-failed,
.save-conflict,
.save-error {
  color: #b04743;
}
.save-error {
  margin: 7px 0 0;
  max-width: 440px;
}
.save-unsaved,
.save-saving {
  color: var(--color-muted);
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
@media (max-width: 650px) {
  .question-heading {
    gap: 10px;
  }
  .question-save {
    flex-direction: column;
  }
  .answer-option {
    padding: 13px;
  }
}
</style>
