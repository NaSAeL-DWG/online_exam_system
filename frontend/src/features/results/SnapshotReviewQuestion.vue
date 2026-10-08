<script setup lang="ts">
import { computed } from 'vue'
import type { ReviewQuestion } from '../../api/results'
import { questionTypeLabels } from '../../api/questions'
import SafeMarkdown from '../../components/SafeMarkdown.vue'
import StatusBadge from '../../components/ui/StatusBadge.vue'
import AnswerContent from '../grading/AnswerContent.vue'

const props = defineProps<{ question: ReviewQuestion; number?: number }>()
const fullScore = computed(
  () =>
    props.question.answer.score !== null &&
    Number(props.question.answer.score) === Number(props.question.score),
)
</script>
<template>
  <article class="review-question" :aria-label="`第 ${number ?? question.display_order} 题`">
    <header class="review-question-header">
      <div>
        <strong>第 {{ number ?? question.display_order }} 题</strong
        ><span class="muted">{{ questionTypeLabels[question.type] }} · {{ question.subject }}</span>
      </div>
      <StatusBadge
        :label="`${question.answer.score ?? '待批改'} / ${question.score} 分`"
        :tone="fullScore ? 'success' : 'warning'"
      />
    </header>
    <div v-if="question.knowledge_tags.length" class="review-tags">
      <span v-for="tag in question.knowledge_tags" :key="tag">{{ tag }}</span>
    </div>
    <SafeMarkdown :content="question.content" />
    <div v-if="question.options.length" class="review-options">
      <div v-for="(option, index) in question.options" :key="option.id">
        <span>{{ String.fromCharCode(65 + index) }}.</span
        ><SafeMarkdown :content="option.content" />
      </div>
    </div>
    <div class="review-answer-grid">
      <section>
        <h3>我的答案</h3>
        <AnswerContent
          :type="question.type"
          :options="question.options"
          :value="question.answer.answer_data"
        />
      </section>
      <section>
        <h3>参考答案</h3>
        <AnswerContent
          :type="question.type"
          :options="question.options"
          :value="question.standard_answer"
          markdown
        />
      </section>
    </div>
    <section v-if="question.explanation" class="review-explanation">
      <h3>解析</h3>
      <SafeMarkdown :content="question.explanation" />
    </section>
    <section v-if="question.answer.grader_comment" class="review-explanation">
      <h3>教师评语</h3>
      <p>{{ question.answer.grader_comment }}</p>
    </section>
  </article>
</template>
<style scoped>
.review-question {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 24px;
  min-width: 0;
}
.review-question-header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 18px;
}
.review-question-header > div {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  font-size: 13px;
}
.review-question-header strong {
  font-size: 15px;
}
.review-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 14px;
}
.review-tags span {
  padding: 3px 8px;
  background: var(--color-bg);
  border-radius: 4px;
  font-size: 12px;
  color: var(--color-muted);
}
.review-options {
  display: grid;
  gap: 10px;
  margin: 18px 0;
}
.review-options > div {
  display: flex;
  gap: 10px;
  align-items: baseline;
  font-size: 14px;
}
.review-answer-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  margin-top: 22px;
}
.review-answer-grid section {
  background: var(--color-bg);
  border-radius: var(--radius-sm);
  padding: 16px;
  min-width: 0;
}
.review-question h3 {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-muted);
}
.review-explanation {
  border-top: 1px solid var(--color-border);
  padding-top: 18px;
  margin-top: 20px;
  font-size: 14px;
}
.review-explanation p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
@media (max-width: 600px) {
  .review-question {
    padding: 18px;
  }
  .review-answer-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }
}
</style>
