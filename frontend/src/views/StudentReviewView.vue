<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { NAlert, NButton } from 'naive-ui'
import { resultsApi } from '../api/results'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
import SnapshotReviewQuestion from '../features/results/SnapshotReviewQuestion.vue'
import { usePrivateResource } from '../features/results/usePrivateResource'
import { examTime } from '../features/attempts/examAvailability'
import '../features/results/results.css'

const route = useRoute()
const onlyMistakes = ref(false)
const { data, loading, failure, load } = usePrivateResource(
  () => route.params.id,
  (signal) => resultsApi.review(String(route.params.id), signal),
)
const questions = computed(() =>
  (data.value?.questions ?? []).filter(
    (question) => !onlyMistakes.value || Number(question.answer.score) < Number(question.score),
  ),
)
const currentIndex = ref(0)
const current = computed(() => questions.value[currentIndex.value])
watch(questions, () => {
  currentIndex.value = 0
})
</script>
<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="RESULTS / ANSWER REVIEW"
      title="答卷回看"
      :description="
        data
          ? `${data.exam_title} / 第 ${data.attempt_no} 次有效作答`
          : '查看已提交答案与公布后的解析。'
      "
    >
      <template #actions
        ><RouterLink :to="data ? `/student/results/${data.exam_id}` : '/student/results'"
          >← 成绩详情</RouterLink
        ><NButton :loading="loading" @click="load">刷新答卷</NButton></template
      >
    </PageHeader>
    <NAlert v-if="failure" type="error">{{ failure }}</NAlert>
    <LoadingSkeleton v-if="loading" variant="detail" label="正在读取授权答卷" />
    <p v-if="!loading && !data" class="result-empty" role="status">
      {{ loading ? '正在读取授权答卷…' : '暂无可查看的答卷。' }}
    </p>
    <template v-if="data">
      <div class="review-layout">
        <div class="review-main">
          <SnapshotReviewQuestion v-if="current" :question="current" />
          <p v-else class="result-empty">本次作答没有未满分题目。</p>
          <div v-if="questions.length" class="review-navigation">
            <NButton :disabled="currentIndex === 0" @click="currentIndex -= 1">← 上一题</NButton>
            <span>{{ currentIndex + 1 }} / {{ questions.length }}</span>
            <NButton :disabled="currentIndex === questions.length - 1" @click="currentIndex += 1"
              >下一题 →</NButton
            >
          </div>
        </div>
        <aside class="review-aside">
          <SurfacePanel title="本次答卷" aria-label="答卷得分">
            <div class="result-score">
              {{ data.final_score ?? '待批改' }} <small>/ {{ data.total_score }} 分</small>
            </div>
            <div class="result-facts">
              <span>第 {{ data.attempt_no }} 次作答</span
              ><span>提交时间：{{ examTime(data.submitted_at) }}</span
              ><span>{{ data.questions.length }} 道快照题目</span
              ><span v-if="current"
                >本题得分 {{ current.answer.score ?? '待批改' }} / {{ current.score }} 分</span
              >
            </div>
            <div class="toolbar review-toolbar">
              <label class="check-field"
                ><input v-model="onlyMistakes" type="checkbox" />仅看未满分题目</label
              ><span class="toolbar-meta">当前 {{ questions.length }} 道题</span>
            </div>
            <nav class="review-question-nav" aria-label="回看题目导航">
              <button
                v-for="(question, index) in questions"
                :key="question.id"
                :aria-label="`回看第 ${question.display_order} 题`"
                :aria-current="index === currentIndex ? 'step' : undefined"
                @click="currentIndex = index"
              >
                {{ String(question.display_order).padStart(2, '0') }}
              </button>
            </nav>
            <p class="review-note">这里展示已提交答案与公布后的解析，答案不可修改。</p>
          </SurfacePanel>
        </aside>
      </div>
    </template>
  </div>
</template>
<style scoped>
.review-toolbar {
  margin: 24px 0 18px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border);
}
.review-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 24px;
  align-items: start;
}
.review-main,
.review-aside {
  min-width: 0;
}
.review-navigation {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
  font-size: 12px;
  color: var(--color-muted);
}
.review-question-nav {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}
.review-question-nav button {
  aspect-ratio: 1;
  border: 1px solid var(--color-border);
  background: white;
  border-radius: 2px;
  color: var(--color-muted);
  cursor: pointer;
  font-family: Consolas, monospace;
}
.review-question-nav button[aria-current] {
  color: white;
  background: var(--color-primary);
  border-color: var(--color-primary);
}
.review-note {
  border-top: 1px solid var(--color-border);
  padding-top: 20px;
  margin: 24px 0 0;
  font-size: 12px;
  color: var(--color-muted);
  line-height: 1.9;
}
@media (max-width: 850px) {
  .review-layout {
    grid-template-columns: 1fr;
  }
}
</style>
