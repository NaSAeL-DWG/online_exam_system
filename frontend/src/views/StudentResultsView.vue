<script setup lang="ts">
import { ref } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { resultsApi, resultStateLabels } from '../api/results'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import ListPager from '../components/ListPager.vue'
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
      title="考试历史"
      description="查看本人各次得分与最终成绩；最终成绩采用最后一次有效提交。"
    >
      <template #actions><NButton :loading="loading" @click="load">刷新结果</NButton></template>
    </PageHeader>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载结果</NButton></NAlert
    >
    <SurfacePanel>
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
      <div class="result-list" :aria-busy="loading">
        <article v-for="item in data?.items" :key="item.exam_id" class="result-row">
          <div class="result-row-copy">
            <RouterLink :to="`/student/results/${item.exam_id}`" class="result-row-title">{{
              item.title
            }}</RouterLink>
            <p>{{ examTime(item.end_at) }} 结束 · {{ item.attempts_count }} 次有效作答</p>
          </div>
          <div class="result-row-meta">
            <span v-if="item.result_state === 'PUBLISHED' && item.final_score !== null"
              ><strong>{{ item.final_score }}</strong> / {{ item.total_score }} 分</span
            >
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
            <RouterLink :to="`/student/results/${item.exam_id}`">查看结果 →</RouterLink>
          </div>
        </article>
        <p v-if="!data?.items.length" class="result-empty" role="status">
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
