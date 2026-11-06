<script setup lang="ts">
import { ref } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { resultsApi, resultStateLabels } from '../api/results'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import ListPager from '../components/ListPager.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
import { usePrivateResource } from '../features/results/usePrivateResource'
import { examTime } from '../features/attempts/examAvailability'
import '../features/results/results.css'

const query = ref('')
const search = ref('')
const page = ref(1)
const { data, loading, failure, load } = usePrivateResource(
  () => [page.value, search.value],
  (signal) => resultsApi.list({ page: page.value, page_size: 20, q: search.value }, signal),
)
function filter(): void {
  const nextSearch = query.value.trim()
  const changed = page.value !== 1 || search.value !== nextSearch
  page.value = 1
  search.value = nextSearch
  // 筛选值变化由 watch 统一读取；相同条件再次提交时才显式刷新。
  if (!changed) void load()
}
</script>
<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="RESULTS / HISTORY"
      title="考试历史"
      description="查看本人各次得分与最终成绩；最终成绩采用最后一次有效提交。"
    >
      <template #actions><NButton :loading="loading" @click="load">刷新结果</NButton></template>
    </PageHeader>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载结果</NButton></NAlert
    >
    <form class="toolbar" @submit.prevent="filter">
      <input
        v-model="query"
        class="form-control toolbar-search"
        aria-label="搜索考试历史"
        placeholder="搜索考试名称"
      />
      <NButton attr-type="submit" :loading="loading">查询历史</NButton>
      <span v-if="data" class="toolbar-meta">共 {{ data.total }} 场考试</span>
    </form>
    <SurfacePanel class="history-panel">
      <div class="result-list" :aria-busy="loading">
        <LoadingSkeleton v-if="loading" label="正在读取最新结果" />
        <div v-if="data?.items.length" class="table-wrap">
          <table class="result-table history-table">
            <thead>
              <tr>
                <th>考试</th>
                <th>最终成绩</th>
                <th>结果状态</th>
                <th>最后提交</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in data.items" :key="item.exam_id">
                <td>
                  <RouterLink :to="`/student/results/${item.exam_id}`" class="history-title">{{
                    item.title
                  }}</RouterLink
                  ><span class="history-subline"
                    >{{ item.attempts_count }} 次有效作答 · {{ examTime(item.end_at) }} 结束</span
                  >
                </td>
                <td class="history-score">
                  <strong>{{
                    item.result_state === 'PUBLISHED' && item.final_score !== null
                      ? `${item.final_score} / ${item.total_score}`
                      : '—'
                  }}</strong>
                </td>
                <td>
                  <StatusBadge
                    :label="resultStateLabels[item.result_state]"
                    :tone="
                      item.result_state === 'PUBLISHED'
                        ? 'success'
                        : item.result_state === 'CORRECTING'
                          ? 'warning'
                          : 'neutral'
                    "
                  />
                </td>
                <td>{{ examTime(item.submitted_at) }}</td>
                <td>
                  <RouterLink :to="`/student/results/${item.exam_id}`">查看详情 →</RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="!loading && !data?.items.length" class="result-empty" role="status">
          {{ loading ? '正在读取最新结果…' : failure ? '结果暂不可读取。' : '暂无考试历史。' }}
        </p>
      </div>
      <ListPager
        v-if="data"
        label="考试"
        :page="page"
        :page-size="20"
        :total="data.total"
        :loading="loading"
        @change="page = $event"
      />
    </SurfacePanel>
  </div>
</template>
<style scoped>
.toolbar {
  margin-bottom: 0;
}
.toolbar-search {
  max-width: 360px;
}
.history-table td:last-child a {
  display: inline-flex;
  border: 1px solid var(--neutral-400);
  padding: 9px 14px;
  color: var(--color-text);
  border-radius: 2px;
}
.history-panel :deep(.surface-panel-body) {
  padding: 0;
}
.history-table {
  min-width: 760px;
}
.history-table th,
.history-table td {
  padding: 18px 24px;
}
.history-table td:first-child {
  width: 38%;
}
.history-table td:first-child > strong {
  font-size: 14px;
  font-weight: 600;
}
.history-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}
.history-subline {
  display: block;
  color: var(--color-muted);
  font-size: 12px;
  margin-top: 7px;
}
.history-score {
  font-family: Consolas, monospace;
  white-space: nowrap;
}
.history-panel :deep(.list-pager) {
  padding: 16px 24px;
}
</style>
