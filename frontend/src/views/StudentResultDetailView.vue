<script setup lang="ts">
import { useRoute } from 'vue-router'
import { NAlert, NButton } from 'naive-ui'
import { resultsApi } from '../api/results'
import { gradingStatusLabels } from '../api/grading'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
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
    <PageHeader
      :title="data?.title || '考试结果'"
      description="最终成绩采用最后一次有效提交；待批改不会按零分计入。"
    >
      <template #actions><NButton :loading="loading" @click="load">刷新结果</NButton></template>
    </PageHeader>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载结果</NButton></NAlert
    >
    <LoadingSkeleton v-if="loading" variant="detail" label="正在读取最新结果" />
    <template v-if="data">
      <div class="result-overview">
        <div class="result-primary">
          <ResultVisibility :state="data.result_state" :allow-review="data.allow_review" />
          <SurfacePanel
            v-if="data.result_state === 'PUBLISHED'"
            title="最终成绩"
            aria-label="最终成绩"
          >
            <NAlert
              v-if="data.final_attempt_id && data.final_score === null"
              type="info"
              title="最后一次作答正在批改"
            >
              批改完成后显示最终成绩，当前不采用此前作答成绩。
            </NAlert>
            <div v-else class="result-score">
              {{ data.final_attempt_id ? data.final_score : '暂无有效提交' }}
              <small v-if="data.final_score !== null">/ {{ data.total_score }} 分</small>
            </div>
            <div class="result-facts">
              <span v-if="data.final_attempt_no">第 {{ data.final_attempt_no }} 次作答</span
              ><span>提交时间：{{ examTime(data.submitted_at) }}</span>
            </div>
          </SurfacePanel>
        </div>
        <SurfacePanel title="本场信息">
          <dl class="result-info">
            <div>
              <dt>考试满分</dt>
              <dd>{{ data.total_score }} 分</dd>
            </div>
            <div>
              <dt>有效作答</dt>
              <dd>{{ data.attempts_count }} 次</dd>
            </div>
            <div>
              <dt>结束时间（上海）</dt>
              <dd>{{ examTime(data.end_at) }}</dd>
            </div>
            <div>
              <dt>答卷回看</dt>
              <dd>{{ data.can_review ? '已开放' : '暂不可回看' }}</dd>
            </div>
          </dl>
        </SurfacePanel>
      </div>
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
<style scoped>
.result-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(250px, 1fr);
  gap: 24px;
  align-items: start;
}
.result-primary {
  display: grid;
  gap: 20px;
  align-content: start;
  min-width: 0;
}
.result-info {
  display: grid;
  gap: 18px;
  margin: 0;
  font-size: 13px;
}
.result-info > div {
  display: grid;
  grid-template-columns: 125px minmax(0, 1fr);
  gap: 12px;
}
.result-info dt {
  color: var(--color-muted);
}
.result-info dd {
  margin: 0;
  overflow-wrap: anywhere;
}
@media (max-width: 850px) {
  .result-overview {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}
</style>
