<script setup lang="ts">
import { computed } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { analyticsApi } from '../api/analytics'
import { mistakesApi } from '../api/mistakes'
import { questionTypeLabels } from '../api/questions'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
import EChartView from '../features/analytics/EChartView.vue'
import { barOption, formatRate, trendOption } from '../features/analytics/chartOptions'
import { usePrivateResource } from '../features/results/usePrivateResource'
import { examTime } from '../features/attempts/examAvailability'
import '../features/analytics/analytics.css'
import '../features/results/results.css'

const { data, loading, failure, load } = usePrivateResource(
  () => 'student-analytics',
  async (signal) => {
    const [analytics, pending, mastered] = await Promise.all([
      analyticsApi.student(signal),
      mistakesApi.list({ page: 1, page_size: 1 }, { mastered: 'false' }, signal).then(
        (result) => result.total,
        () => null,
      ),
      mistakesApi.list({ page: 1, page_size: 1 }, { mastered: 'true' }, signal).then(
        (result) => result.total,
        () => null,
      ),
    ])
    return { ...analytics, pending_mistake_count: pending, mastered_mistake_count: mastered }
  },
)
const averageRate = computed(() => {
  const samples = data.value?.trend ?? []
  return samples.length
    ? `${((samples.reduce((sum, item) => sum + Number(item.score_rate), 0) / samples.length) * 100).toFixed(1)}`
    : '—'
})
const trend = computed(() =>
  trendOption(
    data.value?.trend.map((item) => examTime(item.end_at).split(' ')[0] ?? '未记录日期') ?? [],
    data.value?.trend.map((item) => Number((Number(item.score_rate) * 100).toFixed(1))) ?? [],
    data.value?.trend.map((item) => item.title) ?? [],
  ),
)
const types = computed(() =>
  barOption(
    data.value?.type_performance.map((item) => questionTypeLabels[item.type]) ?? [],
    data.value?.type_performance.map((item) =>
      Number((Number(item.score_rate) * 100).toFixed(1)),
    ) ?? [],
    true,
  ),
)
// 图中展示数量最多的十个知识点，完整记录保留在数据表，避免长标签撑开小屏。
const knowledgeItems = computed(() =>
  [...(data.value?.knowledge_mistakes ?? [])]
    .sort((left, right) => right.count - left.count)
    .slice(0, 10),
)
const knowledge = computed(() =>
  barOption(
    knowledgeItems.value.map((item) => item.knowledge_tag).reverse(),
    knowledgeItems.value.map((item) => item.count).reverse(),
    false,
    true,
  ),
)
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="LEARNING / ANALYTICS"
      title="学习分析"
      description="查看本人已公布成绩的得分率与学习表现；成绩更正后重新读取最新结果。"
    >
      <template #actions><NButton :loading="loading" @click="load">刷新分析</NButton></template>
    </PageHeader>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载分析</NButton></NAlert
    >
    <LoadingSkeleton v-if="loading" variant="detail" label="正在读取本人可见的分析数据" />
    <template v-if="data">
      <dl class="student-analysis-stats" aria-label="学习概况">
        <div>
          <dt>已完成考试</dt>
          <dd>{{ data.sample_exam_count }}<small>场</small></dd>
        </div>
        <div>
          <dt>平均得分率</dt>
          <dd>{{ averageRate }}<small v-if="data.trend.length">%</small></dd>
        </div>
        <div>
          <dt>待复习错题</dt>
          <dd>
            {{ data.pending_mistake_count ?? '—'
            }}<small>{{ data.pending_mistake_count === null ? '暂不可读取' : '题' }}</small>
          </dd>
        </div>
        <div>
          <dt>已掌握错题</dt>
          <dd>
            {{ data.mastered_mistake_count ?? '—'
            }}<small>{{ data.mastered_mistake_count === null ? '暂不可读取' : '题' }}</small>
          </dd>
        </div>
      </dl>
      <div class="student-analysis-primary">
        <SurfacePanel
          title="最终得分率趋势"
          description="按考试结束时间升序排列；每场采用最后一次有效提交的得分 ÷ 本场满分。"
        >
          <EChartView
            v-if="data.trend.length"
            :option="trend"
            label="最终得分率趋势图"
            kind="line"
          />
          <p v-else class="result-empty" role="status">暂无已公布的最终成绩。</p>
          <details v-if="data.trend.length" class="analytics-data">
            <summary>查看趋势数据</summary>
            <div class="table-wrap">
              <table class="result-table">
                <thead>
                  <tr>
                    <th>考试</th>
                    <th>结束时间</th>
                    <th>最终成绩／满分</th>
                    <th>得分率</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in data.trend" :key="item.exam_id">
                    <td>
                      <RouterLink :to="`/student/results/${item.exam_id}`">{{
                        item.title
                      }}</RouterLink>
                    </td>
                    <td>{{ examTime(item.end_at) }}</td>
                    <td>{{ item.final_score }} / {{ item.total_score }}</td>
                    <td>{{ formatRate(item.score_rate) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </details>
        </SurfacePanel>
        <SurfacePanel
          title="优先复习的知识点"
          description="按错误作答记录数排序，同一道题的各次错误分别保留。"
        >
          <div v-if="knowledgeItems.length" class="knowledge-priority">
            <div
              v-for="item in knowledgeItems.slice(0, 5)"
              :key="item.knowledge_tag"
              class="knowledge-priority-row"
            >
              <span>{{ item.knowledge_tag }}</span>
              <div class="knowledge-track">
                <span
                  :style="{ width: `${(item.count / (knowledgeItems[0]?.count || 1)) * 100}%` }"
                />
              </div>
              <strong>{{ item.count }} 题</strong>
            </div>
          </div>
          <p v-else class="result-empty">暂无可见的知识点错题记录。</p>
          <RouterLink class="mistakes-link" to="/student/mistakes">进入错题复习 →</RouterLink>
        </SurfacePanel>
      </div>
      <p class="analytics-note">
        总分趋势包含 {{ data.sample_exam_count }} 场已公布考试；题型表现与知识点错题仅使用
        {{ data.review_exam_count }} 场允许回看的考试。平均得分率按各场得分率取平均。
      </p>
      <div class="analytics-grid">
        <SurfacePanel
          title="题型表现"
          description="仅使用允许回看的最终作答，按该题型得分和 ÷ 满分和计算。"
        >
          <EChartView v-if="data.type_performance.length" :option="types" label="题型得分率图" />
          <p v-else class="result-empty" role="status">暂无允许回看的题型数据。</p>
          <details v-if="data.type_performance.length" class="analytics-data">
            <summary>查看题型数据</summary>
            <div class="table-wrap">
              <table class="result-table">
                <thead>
                  <tr>
                    <th>题型</th>
                    <th>答题数</th>
                    <th>得分和／满分和</th>
                    <th>得分率</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in data.type_performance" :key="item.type">
                    <td>{{ questionTypeLabels[item.type] }}</td>
                    <td>{{ item.answer_count }}</td>
                    <td>{{ item.score_sum }} / {{ item.full_score_sum }}</td>
                    <td>{{ formatRate(item.score_rate) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </details>
        </SurfacePanel>
        <SurfacePanel
          title="知识点错题分布"
          description="一题多标签可分别计入；数量按错误作答记录统计。"
        >
          <EChartView
            v-if="data.knowledge_mistakes.length"
            :option="knowledge"
            label="知识点错题分布图"
          />
          <p v-else class="result-empty" role="status">暂无可见的知识点错题记录。</p>
          <p v-if="data.knowledge_mistakes.length > 10" class="analytics-note">
            图中展示错题数最多的 10 个知识点，完整数据见下表。
          </p>
          <p class="analytics-note">{{ data.knowledge_note }}</p>
          <details v-if="data.knowledge_mistakes.length" class="analytics-data">
            <summary>查看知识点数据</summary>
            <div class="table-wrap">
              <table class="result-table">
                <thead>
                  <tr>
                    <th>知识点</th>
                    <th>错误作答记录数</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in data.knowledge_mistakes" :key="item.knowledge_tag">
                    <td>{{ item.knowledge_tag }}</td>
                    <td>{{ item.count }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </details>
        </SurfacePanel>
      </div>
    </template>
  </div>
</template>

<style scoped>
.student-analysis-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin: 0;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}
.student-analysis-stats > div {
  padding: 22px 24px;
  border-right: 1px solid var(--color-border);
}
.student-analysis-stats > div:last-child {
  border-right: 0;
}
.student-analysis-stats dt {
  color: var(--color-muted);
  font-size: 12px;
}
.student-analysis-stats dd {
  margin: 8px 0 0;
  color: var(--blue-700);
  font:
    29px Consolas,
    monospace;
  line-height: 1.4;
}
.student-analysis-stats small {
  margin-left: 7px;
  font-size: 11px;
  color: var(--color-muted);
}
.student-analysis-primary {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 1fr);
  gap: 24px;
}
.student-analysis-primary > * {
  min-width: 0;
}
.student-analysis-primary :deep(.analytics-chart) {
  height: 240px;
}
.knowledge-priority {
  display: grid;
  gap: 28px;
  margin: 14px 0 28px;
}
.knowledge-priority-row {
  display: grid;
  grid-template-columns: 90px minmax(0, 1fr) 34px;
  gap: 12px;
  align-items: center;
  font-size: 12px;
}
.knowledge-priority-row strong {
  font-weight: 400;
  font-family: Consolas, monospace;
}
.knowledge-track {
  background: var(--neutral-200);
  height: 6px;
}
.knowledge-track > span {
  display: block;
  height: 100%;
  background: var(--color-primary);
}
.mistakes-link {
  display: inline-block;
  margin-top: 10px;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: 2px;
  color: var(--color-text);
  font-size: 13px;
}
@media (max-width: 950px) {
  .student-analysis-primary {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 600px) {
  .student-analysis-stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .student-analysis-stats > div {
    padding: 18px;
  }
  .student-analysis-stats > div:nth-child(2) {
    border-right: 0;
  }
  .student-analysis-stats > div:nth-child(-n + 2) {
    border-bottom: 1px solid var(--color-border);
  }
}
</style>
