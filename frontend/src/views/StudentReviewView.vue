<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { NAlert, NButton } from 'naive-ui'
import { resultsApi } from '../api/results'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
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
</script>
<template>
  <div class="page-stack">
    <RouterLink :to="data ? `/student/results/${data.exam_id}` : '/student/results'"
      >← 返回考试结果</RouterLink
    >
    <PageHeader
      :title="data?.exam_title || '答卷回看'"
      description="回看本次作答的考试快照，来源题库的后续修改不会改变这里的内容。"
    >
      <template #actions><NButton :loading="loading" @click="load">刷新答卷</NButton></template>
    </PageHeader>
    <NAlert v-if="failure" type="error">{{ failure }}</NAlert>
    <p v-if="!data" class="result-empty" role="status">
      {{ loading ? '正在读取授权答卷…' : '暂无可查看的答卷。' }}
    </p>
    <template v-if="data">
      <SurfacePanel title="答卷得分" aria-label="答卷得分">
        <div class="result-score">
          {{ data.final_score ?? '待批改' }} <small>/ {{ data.total_score }} 分</small>
        </div>
        <div class="result-facts">
          <span>第 {{ data.attempt_no }} 次作答</span
          ><span>提交时间：{{ examTime(data.submitted_at) }}</span
          ><span>{{ data.questions.length }} 道快照题目</span>
        </div>
      </SurfacePanel>
      <div class="toolbar review-toolbar">
        <label class="check-field"
          ><input v-model="onlyMistakes" type="checkbox" />仅看未满分题目</label
        ><span class="toolbar-meta">当前 {{ questions.length }} 道题</span>
      </div>
      <SnapshotReviewQuestion
        v-for="question in questions"
        :key="question.id"
        :question="question"
      />
      <p v-if="!questions.length" class="result-empty">本次作答没有未满分题目。</p>
    </template>
  </div>
</template>
<style scoped>
.review-toolbar {
  margin-bottom: 0;
}
</style>
