<script setup lang="ts">
import { computed, useId } from 'vue'
import { NButton } from 'naive-ui'
import type { QuestionInput } from '../../api/questions'
import type { ContentFieldErrors } from '../contentValidation'
const model = defineModel<QuestionInput>({ required: true })
defineProps<{ errors?: ContentFieldErrors }>()
const errorPrefix = useId()
const isChoice = computed(() => ['SINGLE_CHOICE', 'MULTIPLE_CHOICE'].includes(model.value.type))
function selectAnswer(id: string, checked: boolean): void {
  if (model.value.type === 'SINGLE_CHOICE') {
    model.value.standard_answer = [id]
    return
  }
  const answer = Array.isArray(model.value.standard_answer) ? model.value.standard_answer : []
  model.value.standard_answer = checked ? [...answer, id] : answer.filter((item) => item !== id)
}
function removeOption(id: string): void {
  model.value.options = model.value.options.filter((option) => option.id !== id)
  if (Array.isArray(model.value.standard_answer))
    model.value.standard_answer = model.value.standard_answer.filter((item) => item !== id)
}
function addOption(): void {
  model.value.options.push({ id: crypto.randomUUID(), content: '' })
}
</script>

<template>
  <section aria-labelledby="answer-title">
    <div class="section-heading">
      <h3 id="answer-title">答案设置</h3>
      <p class="muted">
        {{
          isChoice
            ? model.type === 'MULTIPLE_CHOICE'
              ? '勾选至少两个正确选项；选项内容必填。'
              : '选择一个正确选项；选项内容必填。'
            : model.type === 'TRUE_FALSE'
              ? '选择此题的判断结果。'
              : '参考答案可选，用于人工阅卷。'
        }}
      </p>
    </div>
    <div v-if="isChoice" class="options-editor">
      <div v-for="(option, index) in model.options" :key="option.id" class="option-line">
        <label class="answer-check"
          ><input
            :type="model.type === 'SINGLE_CHOICE' ? 'radio' : 'checkbox'"
            name="correct-option"
            :aria-label="`正确选项 ${index + 1}`"
            :checked="
              Array.isArray(model.standard_answer) && model.standard_answer.includes(option.id)
            "
            :aria-invalid="!!errors?.standard_answer"
            :aria-describedby="errors?.standard_answer ? `${errorPrefix}-answer-error` : undefined"
            @change="selectAnswer(option.id, ($event.target as HTMLInputElement).checked)"
          /><span>{{ String.fromCharCode(65 + index) }}</span></label
        >
        <label class="field option-content"
          ><span class="sr-only">选项 {{ index + 1 }}</span
          ><input
            v-model="option.content"
            :aria-label="`选项 ${index + 1}`"
            :placeholder="`选项 ${index + 1} 的内容`"
            required
            maxlength="20000"
            :aria-invalid="!!errors?.[`option.${option.id}`]"
            :aria-describedby="
              errors?.[`option.${option.id}`] ? `${errorPrefix}-${option.id}-error` : undefined
            "
          /><span
            v-if="errors?.[`option.${option.id}`]"
            :id="`${errorPrefix}-${option.id}-error`"
            class="field-error"
            role="alert"
            >{{ errors[`option.${option.id}`] }}</span
          ></label
        >
        <NButton size="small" :disabled="model.options.length <= 2" @click="removeOption(option.id)"
          >移除</NButton
        >
      </div>
      <p
        v-if="errors?.standard_answer"
        :id="`${errorPrefix}-answer-error`"
        class="field-error"
        role="alert"
      >
        {{ errors.standard_answer }}
      </p>
      <NButton :disabled="model.options.length >= 8" @click="addOption">增加选项</NButton>
    </div>
    <label v-else-if="model.type === 'TRUE_FALSE'" class="field"
      >判断答案<select v-model="model.standard_answer" aria-label="判断答案">
        <option :value="true">真</option>
        <option :value="false">假</option>
      </select></label
    >
    <label v-else class="field"
      >参考答案（可选）<textarea
        :value="typeof model.standard_answer === 'string' ? model.standard_answer : ''"
        aria-label="参考答案"
        rows="4"
        @input="model.standard_answer = ($event.target as HTMLTextAreaElement).value || null"
      />
    </label>
  </section>
</template>

<style scoped>
.section-heading {
  margin-bottom: 14px;
}
.field-error {
  color: #b42318;
  font-size: 12px;
}
h3,
p {
  margin: 0;
}
p {
  margin-top: 4px;
  font-size: 13px;
}
.options-editor {
  display: grid;
  gap: 10px;
  justify-items: start;
}
.option-line {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 12px;
}
.option-content {
  flex: 1;
  min-width: 0;
}
.answer-check {
  display: flex;
  gap: 8px;
  align-items: center;
  font-weight: 600;
}
.answer-check input {
  width: 16px;
  height: 16px;
  accent-color: var(--color-primary);
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
@media (max-width: 520px) {
  .option-line {
    gap: 8px;
  }
}
</style>
