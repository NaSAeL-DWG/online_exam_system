<script setup lang="ts">
import { computed } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { analyticsApi } from '../api/analytics'
import { questionTypeLabels } from '../api/questions'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import EChartView from '../features/analytics/EChartView.vue'
import { barOption, formatRate, trendOption } from '../features/analytics/chartOptions'
import { usePrivateResource } from '../features/results/usePrivateResource'
import { examTime } from '../features/attempts/examAvailability'
import '../features/analytics/analytics.css'
import '../features/results/results.css'

const { data, loading, failure, load } = usePrivateResource(
  () => 'student-analytics',
  (signal) => analyticsApi.student(signal),
)
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
      title="学习分析"
      description="查看本人已公布成绩的得分率与学习表现；成绩更正后重新读取最新结果。"
    >
      <template #actions><NButton :loading="loading" @click="load">刷新分析</NButton></template>
    </PageHeader>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载分析</NButton></NAlert
    >
    <p v-if="loading" class="muted" role="status">正在读取本人可见的分析数据…</p>
    <template v-if="data">
      <SurfacePanel
        title="分析范围"
        description="只包含本人有效且已公布的记录，不提供其他同学的具体成绩或排名。"
      >
        <dl class="student-analysis-scope">
          <div>
            <dt>最终成绩样本</dt>
            <dd>{{ data.sample_exam_count }} <small>场考试</small></dd>
          </div>
          <div>
            <dt>允许回看的题目样本</dt>
            <dd>{{ data.review_exam_count }} <small>场考试</small></dd>
          </div>
        </dl>
        <p class="analytics-note">
          总分趋势包含已公布成绩；题型表现与知识点错题仅使用允许回看的考试。
        </p>
      </SurfacePanel>
      <SurfacePanel
        title="最终得分率趋势"
        description="按考试结束时间升序排列；每场采用最后一次有效提交的得分 ÷ 本场满分。"
      >
        <EChartView v-if="data.trend.length" :option="trend" label="最终得分率趋势图" kind="line" />
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
.student-analysis-scope {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
  margin: 0;
}
.student-analysis-scope dt {
  color: var(--color-muted);
  font-size: 12px;
  margin-bottom: 9px;
}
.student-analysis-scope dd {
  margin: 0;
  font-size: 24px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}
.student-analysis-scope small {
  font-size: 12px;
  color: var(--color-muted);
  font-weight: 400;
}
</style>
