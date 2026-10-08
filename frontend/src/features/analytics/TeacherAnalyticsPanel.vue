<script setup lang="ts">
import { computed } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { analyticsApi } from '../../api/analytics'
import { questionTypeLabels } from '../../api/questions'
import SurfacePanel from '../../components/ui/SurfacePanel.vue'
import { usePrivateResource } from '../results/usePrivateResource'
import EChartView from './EChartView.vue'
import { barOption, formatRate } from './chartOptions'
import './analytics.css'
import '../results/results.css'

const props = defineProps<{ examId: string }>()
const { data, loading, failure, load } = usePrivateResource(
  () => props.examId,
  (signal) => analyticsApi.teacher(props.examId, signal),
)
const distribution = computed(() =>
  barOption(
    data.value?.score_distribution.map((item) => item.label) ?? [],
    data.value?.score_distribution.map((item) => item.count) ?? [],
  ),
)
</script>
<template>
  <div class="page-stack">
    <div class="toolbar">
      <NButton :loading="loading" @click="load">刷新统计</NButton
      ><span class="toolbar-meta">打开时汇总当前记录，重新公布后读取最新结果。</span>
    </div>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载统计</NButton></NAlert
    >
    <p v-if="loading" class="muted" role="status">正在汇总本场考试…</p>
    <template v-if="data">
      <SurfacePanel
        title="人数统计"
        aria-label="人数统计"
        description="按学生去重，多次作答不重复计人数。"
      >
        <dl class="metric-grid">
          <div>
            <dt>应考人数</dt>
            <dd :class="{ 'metric-empty': data.expected_count === null }">
              {{ data.expected_count ?? '不适用' }}
            </dd>
          </div>
          <div>
            <dt>参考人数</dt>
            <dd>{{ data.participated_count }}</dd>
          </div>
          <div>
            <dt>提交人数</dt>
            <dd>{{ data.submitted_count }}</dd>
          </div>
          <div>
            <dt>缺考人数</dt>
            <dd :class="{ 'metric-empty': data.absent_count === null }">
              {{ data.absent_count ?? (data.audience_type === 'PUBLIC' ? '不适用' : '结束后确定') }}
            </dd>
          </div>
          <div>
            <dt>作答中人数</dt>
            <dd>{{ data.in_progress_count }}</dd>
          </div>
          <div>
            <dt>待批改人数</dt>
            <dd>{{ data.pending_grading_count }}</dd>
          </div>
          <div>
            <dt>已判完样本数</dt>
            <dd>{{ data.graded_count }}</dd>
          </div>
          <div>
            <dt>参考率</dt>
            <dd :class="{ 'metric-empty': data.participation_rate === null }">
              {{ data.audience_type === 'PUBLIC' ? '不适用' : formatRate(data.participation_rate) }}
            </dd>
          </div>
        </dl>
        <p v-if="data.audience_type === 'PUBLIC'" class="analytics-note">
          公开考试无固定应考分母，不计算缺考或参考率。
        </p>
      </SurfacePanel>
      <SurfacePanel
        title="成绩指标"
        aria-label="成绩指标"
        :description="`仅采用每人的最后一次有效提交，已判完样本 ${data.graded_count} 人；满分 ${data.total_score} 分，及格线 ${data.pass_percentage}%。`"
      >
        <dl class="metric-grid">
          <div>
            <dt>平均分</dt>
            <dd :class="{ 'metric-empty': data.average_score === null }">
              {{ data.average_score ?? '暂无数据' }}
            </dd>
          </div>
          <div>
            <dt>最高分</dt>
            <dd :class="{ 'metric-empty': data.highest_score === null }">
              {{ data.highest_score ?? '暂无数据' }}
            </dd>
          </div>
          <div>
            <dt>最低分</dt>
            <dd :class="{ 'metric-empty': data.lowest_score === null }">
              {{ data.lowest_score ?? '暂无数据' }}
            </dd>
          </div>
          <div>
            <dt>及格率</dt>
            <dd :class="{ 'metric-empty': data.pass_rate === null }">
              {{ formatRate(data.pass_rate) }}
            </dd>
          </div>
        </dl>
        <p v-if="!data.graded_count" class="analytics-note">暂无已判完的最终作答样本。</p>
      </SurfacePanel>
      <SurfacePanel title="最终成绩分布" description="按最终得分率分组；待批改或未提交不计为零分。">
        <EChartView v-if="data.graded_count" :option="distribution" label="最终成绩分布图" />
        <p v-else class="result-empty">暂无成绩分布数据。</p>
        <div v-if="data.graded_count" class="analytics-data">
          <details>
            <summary>查看分布数据</summary>
            <div class="table-wrap">
              <table class="result-table">
                <thead>
                  <tr>
                    <th>得分率区间</th>
                    <th>人数</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in data.score_distribution" :key="item.label">
                    <td>{{ item.label }}</td>
                    <td>{{ item.count }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </details>
        </div>
      </SurfacePanel>
      <SurfacePanel
        title="逐题得分率"
        description="已判完最终作答的该题得分和 ÷（样本人数 × 该题满分）。"
      >
        <div class="table-wrap">
          <table class="result-table">
            <thead>
              <tr>
                <th>快照题目</th>
                <th>题型／科目</th>
                <th>满分</th>
                <th>样本数</th>
                <th>得分和</th>
                <th>得分率</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="question in data.question_rates" :key="question.question_id">
                <td>第 {{ question.order_no }} 题</td>
                <td>{{ questionTypeLabels[question.type] }} / {{ question.subject }}</td>
                <td>{{ question.full_score }}</td>
                <td>{{ question.sample_count }}</td>
                <td>{{ question.score_sum }}</td>
                <td>
                  {{ formatRate(question.score_rate)
                  }}<span v-if="question.score_rate !== null" class="rate-track"
                    ><span :style="{ width: `${Number(question.score_rate) * 100}%` }"
                  /></span>
                </td>
              </tr>
              <tr v-if="!data.question_rates.length">
                <td colspan="6">暂无快照题目。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </SurfacePanel>
      <SurfacePanel
        title="作答与任务"
        aria-label="作答与任务"
        description="作答和阅卷任务按份计数，与人数指标区分。"
        ><dl class="metric-grid">
          <div>
            <dt>有效作答次数</dt>
            <dd>{{ data.attempts_count }}</dd>
          </div>
          <div>
            <dt>已提交答卷</dt>
            <dd>{{ data.submitted_attempts_count }}</dd>
          </div>
          <div>
            <dt>阅卷任务</dt>
            <dd>{{ data.grading_tasks_count }}</dd>
          </div>
          <div>
            <dt>未完阅卷任务</dt>
            <dd>{{ data.pending_grading_tasks_count }}</dd>
          </div>
        </dl></SurfacePanel
      >
      <SurfacePanel v-if="data.notes.length" title="统计口径"
        ><ul class="analytics-notes">
          <li v-for="note in data.notes" :key="note">{{ note }}</li>
        </ul></SurfacePanel
      >
    </template>
  </div>
</template>
