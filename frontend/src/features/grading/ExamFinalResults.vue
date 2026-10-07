<script setup lang="ts">
import { NAlert, NButton } from 'naive-ui'
import { gradingApi, gradingStatusLabels } from '../../api/grading'
import { usePagedList } from '../../composables/usePagedList'
import StatusBadge from '../../components/ui/StatusBadge.vue'
import ListPager from '../../components/ListPager.vue'
import './grading.css'
const props = defineProps<{ examId: string }>()
const { items, page, total, query, loading, failure, load, changePage } = usePagedList((query) =>
  gradingApi.finalResults(props.examId, query),
)
</script>
<template>
  <p class="result-definition">最终成绩取最后一次有效提交；该次待批改时不显示此前成绩。</p>
  <form class="toolbar" @submit.prevent="changePage(1)">
    <input
      v-model="query"
      class="form-control toolbar-search"
      aria-label="搜索成绩学生"
      placeholder="搜索学生姓名或学号"
    /><NButton attr-type="submit" :loading="loading">查询最终成绩</NButton>
  </form>
  <NAlert v-if="failure" type="error"
    >{{ failure }} <NButton size="small" @click="load">重试加载成绩</NButton></NAlert
  >
  <div class="table-region" :aria-busy="loading">
    <table class="grading-table final-results-table">
      <thead>
        <tr>
          <th>学生</th>
          <th>最终成绩</th>
          <th>最后有效提交</th>
          <th>判分状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="result in items" :key="result.participant_id">
          <td>
            {{ result.student.real_name
            }}<span class="table-subtitle">{{ result.student.login_name }}</span>
          </td>
          <td>
            <strong
              v-if="result.grading_status === 'GRADED' && result.final_score !== null"
              class="score-value"
              >{{ result.final_score }} 分</strong
            ><span v-else class="muted">{{ result.attempt_id ? '待批改' : '暂无成绩' }}</span>
          </td>
          <td>
            {{ result.attempt_no === null ? '尚无有效提交' : `第 ${result.attempt_no} 次作答` }}
          </td>
          <td>
            <StatusBadge
              :label="result.grading_status ? gradingStatusLabels[result.grading_status] : '未提交'"
              :tone="result.grading_status === 'GRADED' ? 'success' : 'warning'"
            />
          </td>
          <td>
            <RouterLink v-if="result.attempt_id" :to="`/staff/attempts/${result.attempt_id}`"
              >查看本次答卷 →</RouterLink
            ><span v-else class="muted">—</span>
          </td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="5" class="empty-state">
            {{ loading ? '正在读取成绩…' : '暂无有效参考学生。' }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <ListPager
    label="最终成绩"
    :page="page"
    :total="total"
    :page-size="20"
    :loading="loading"
    @change="changePage"
  />
</template>
<style scoped>
.result-definition {
  margin: 0 0 20px;
  color: var(--color-muted);
  font-size: 13px;
}
@media (max-width: 700px) {
  .final-results-table th:first-child,
  .final-results-table td:first-child {
    width: 150px;
    max-width: 150px;
    overflow-wrap: anywhere;
  }
  .final-results-table th:nth-child(2),
  .final-results-table td:nth-child(2) {
    width: 100px;
    white-space: nowrap;
  }
}
</style>
