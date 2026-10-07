<script setup lang="ts">
import { NButton } from 'naive-ui'
import type { SnapshotQuestion } from '../../api/exams'
import { questionTypeLabels } from '../../api/questions'
import SafeMarkdown from '../../components/SafeMarkdown.vue'
import QuestionPicker from '../../components/QuestionPicker.vue'
import type { Question } from '../../api/questions'
const model = defineModel<SnapshotQuestion[]>({ required: true })
defineProps<{ disabled: boolean; allowCorrection?: boolean }>()
const emit = defineEmits<{
  move: [index: number, direction: number]
  edit: [index: number]
  add: [question: Question]
  correct: [index: number]
}>()
</script>
<template>
  <div class="snapshot-workspace" :class="{ 'snapshot-workspace--locked': disabled }">
    <section data-testid="exam-snapshot" class="snapshot-list" aria-label="考试题目快照">
      <p v-if="!model.length" class="snapshot-empty">当前没有题目，请从题库加入题目后保存。</p>
      <article
        v-for="(question, index) in model"
        :key="question.id ?? question.source_question_id ?? index"
        class="snapshot-question"
      >
        <header class="question-heading">
          <span class="question-number">{{ String(index + 1).padStart(2, '0') }}</span>
          <div>
            <strong>第 {{ index + 1 }} 题</strong>
            <p class="muted">{{ questionTypeLabels[question.type] }} · {{ question.subject }}</p>
          </div>
        </header>
        <SafeMarkdown :content="question.content" />
        <div class="question-controls">
          <label class="score-field"
            >分值<input
              v-model="question.score"
              class="form-control"
              :aria-label="`快照第 ${index + 1} 题分值`"
              type="number"
              min="0.1"
              step="0.1"
              required
              :disabled="disabled"
            /><span class="muted">分</span></label
          >
          <div v-if="!disabled" class="question-actions">
            <NButton
              size="small"
              :aria-label="`编辑快照第 ${index + 1} 题`"
              @click="emit('edit', index)"
              >编辑题目</NButton
            ><NButton
              size="small"
              :aria-label="`上移快照第 ${index + 1} 题`"
              :disabled="index === 0"
              @click="emit('move', index, -1)"
              >上移</NButton
            ><NButton
              size="small"
              :aria-label="`下移快照第 ${index + 1} 题`"
              :disabled="index === model.length - 1"
              @click="emit('move', index, 1)"
              >下移</NButton
            ><NButton size="small" @click="model.splice(index, 1)">移出</NButton>
          </div>
          <NButton
            v-if="allowCorrection"
            size="small"
            :aria-label="`更正第 ${index + 1} 题评分依据`"
            @click="emit('correct', index)"
            >更正评分依据</NButton
          >
        </div>
      </article>
    </section>
    <aside v-if="!disabled" class="snapshot-picker">
      <QuestionPicker
        :excluded-ids="
          model.flatMap((question) =>
            question.source_question_id ? [question.source_question_id] : [],
          )
        "
        @add="emit('add', $event)"
      />
    </aside>
  </div>
</template>
<style scoped>
.snapshot-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  gap: 26px;
  align-items: start;
}
.snapshot-list {
  display: grid;
  gap: 14px;
  min-width: 0;
}
.snapshot-workspace--locked {
  grid-template-columns: 1fr;
}
.snapshot-question {
  padding: 18px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  min-width: 0;
}
.question-heading {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}
.question-heading p {
  margin: 3px 0 0;
  font-size: 12px;
}
.question-number {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: 5px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 700;
}
.question-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--color-border);
}
.score-field {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.score-field input {
  width: 80px;
}
.question-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.snapshot-picker {
  min-width: 0;
  padding-left: 24px;
  border-left: 1px solid var(--color-border);
}
.snapshot-empty {
  text-align: center;
  color: var(--color-muted);
  padding: 32px 16px;
  border: 1px dashed var(--color-border);
}
@media (max-width: 1050px) {
  .snapshot-workspace {
    grid-template-columns: 1fr;
  }
  .snapshot-picker {
    padding: 24px 0 0;
    border: 0;
    border-top: 1px solid var(--color-border);
  }
}
</style>
