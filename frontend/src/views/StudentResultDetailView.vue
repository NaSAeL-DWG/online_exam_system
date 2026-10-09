<script setup lang="ts">
import { useRoute } from 'vue-router'
import { NAlert, NButton } from 'naive-ui'
import { resultsApi } from '../api/results'
import { gradingStatusLabels } from '../api/grading'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import ResultVisibility from '../features/results/ResultVisibility.vue'
import { usePrivateResource } from '../features/results/usePrivateResource'
import { examTime } from '../features/attempts/examAvailability'
import '../features/results/results.css'

const route = useRoute()
const { data, loading, failure, load } = usePrivateResource(
  () => route.params.id,
  (signal) => resultsApi.detail(String(route.params.id), signal),
)
</script>
<template>
  <div class="page-stack">
    <RouterLink to="/student/results">← 返回考试历史</RouterLink>
    <PageHeader :title="data?.title || '考试结果'">
      <template #actions><NButton :loading="loading" @click="load">刷新结果</NButton></template>
    </PageHeader>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载结果</NButton></NAlert
    >
    <p v-if="loading" class="muted" role="status">正在读取最新结果…</p>
    <template v-if="data">
      <ResultVisibility :state="data.result_state" :allow-review="data.allow_review" />
      <SurfacePanel
        v-if="data.result_state === 'PUBLISHED'"
        title="最终成绩"
        aria-label="最终成绩"
        description="取最后一次有效提交；该次待批改时不采用此前成绩。"
      >
        <div class="result-score">
          {{ data.final_attempt_id ? (data.final_score ?? '待批改') : '暂无有效提交' }}
          <small v-if="data.final_score !== null">/ {{ data.total_score }} 分</small>
        </div>
        <div class="result-facts">
          <span v-if="data.final_attempt_no">第 {{ data.final_attempt_no }} 次作答</span
          ><span>提交时间：{{ examTime(data.submitted_at) }}</span>
        </div>
      </SurfacePanel>
      <SurfacePanel title="各次作答" description="所有有效作答分别保留，废弃作答不参与本场结果。">
        <div v-if="data.attempts.length" class="table-wrap">
          <table class="result-table">
            <thead>
              <tr>
                <th>作答</th>
                <th>本次得分</th>
                <th>状态</th>
                <th>提交时间</th>
                <th>答卷</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="attempt in data.attempts" :key="attempt.id">
                <td>
                  第 {{ attempt.attempt_no }} 次
                  <span v-if="attempt.id === data.final_attempt_id" class="muted">（最终）</span>
                </td>
                <td>
                  {{
                    data.result_state === 'PUBLISHED' ? (attempt.final_score ?? '待批改') : '未开放'
                  }}
                </td>
                <td>
                  {{
                    attempt.status === 'IN_PROGRESS'
                      ? '作答中'
                      : gradingStatusLabels[attempt.grading_status]
                  }}
                </td>
                <td>{{ examTime(attempt.submitted_at) }}</td>
                <td>
                  <RouterLink
                    v-if="attempt.can_review"
                    :to="`/student/attempts/${attempt.id}/review`"
                    >回看答卷</RouterLink
                  ><span v-else class="muted">暂不可回看</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="result-empty">暂无有效作答。</p>
      </SurfacePanel>
    </template>
  </div>
</template>
