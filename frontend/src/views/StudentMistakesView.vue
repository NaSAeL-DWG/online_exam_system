<script setup lang="ts">
import { reactive, ref } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import NSelect from '../components/ui/AppSelect.vue'
import { mistakesApi, type MistakeFilters } from '../api/mistakes'
import { questionTypeLabels } from '../api/questions'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import SafeMarkdown from '../components/SafeMarkdown.vue'
import ListPager from '../components/ListPager.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
import { usePrivateResource } from '../features/results/usePrivateResource'
import '../features/results/results.css'

const filters = reactive<MistakeFilters>({
  q: '',
  subject: '',
  type: '',
  knowledge_tag: '',
  mastered: '',
})
const applied = ref<MistakeFilters>({})
const typeOptions = [
  { label: '全部题型', value: '' },
  ...Object.entries(questionTypeLabels).map(([value, label]) => ({ label, value })),
]
const masteryOptions = [
  { label: '全部掌握情况', value: '' },
  { label: '待复习', value: 'false' },
  { label: '已掌握', value: 'true' },
]
const page = ref(1)
const { data, loading, failure, load } = usePrivateResource(
  () => [page.value, applied.value],
  (signal) =>
    mistakesApi.list(
      { page: page.value, page_size: 20, q: applied.value.q },
      applied.value,
      signal,
    ),
)
function filter(): void {
  page.value = 1
  applied.value = { ...filters }
}
function clearFilters(): void {
  Object.assign(filters, { q: '', subject: '', type: '', knowledge_tag: '', mastered: '' })
  filter()
}
</script>
<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="LEARNING / MISTAKES"
      title="我的错题"
      description="每次未满分作答分别保留；后次答对不会删除前次错误，掌握标记不改变成绩。"
    >
      <template #actions><NButton :loading="loading" @click="load">刷新错题</NButton></template>
    </PageHeader>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载错题</NButton></NAlert
    >
    <form class="mistake-filters" @submit.prevent="filter">
      <label class="field"
        >搜索<input v-model="filters.q" aria-label="搜索错题" placeholder="考试名称或题干"
      /></label>
      <label class="field"
        >科目<input v-model="filters.subject" aria-label="科目筛选" placeholder="科目名称"
      /></label>
      <div class="field">
        <label for="mistake-type">题型</label
        ><NSelect
          id="mistake-type"
          v-model:value="filters.type"
          :options="typeOptions"
          aria-label="题型筛选"
        />
      </div>
      <label class="field"
        >知识点<input
          v-model="filters.knowledge_tag"
          aria-label="知识点筛选"
          placeholder="知识点标签"
      /></label>
      <div class="field">
        <label for="mistake-mastery">掌握情况</label
        ><NSelect
          id="mistake-mastery"
          v-model:value="filters.mastered"
          :options="masteryOptions"
          aria-label="掌握状态"
        />
      </div>
      <div class="filter-actions">
        <NButton type="primary" attr-type="submit" :loading="loading">筛选错题</NButton
        ><NButton :disabled="loading" @click="clearFilters">清除筛选</NButton>
      </div>
    </form>
    <SurfacePanel class="mistakes-panel">
      <div class="result-list" :aria-busy="loading">
        <LoadingSkeleton v-if="loading" label="正在读取可见错题" />
        <div v-if="data?.items.length" class="table-wrap">
          <table class="result-table mistakes-table">
            <thead>
              <tr>
                <th>题目与知识点</th>
                <th>来源考试</th>
                <th>题型</th>
                <th>复习状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in data.items" :key="item.answer_id">
                <td>
                  <div class="mistake-content"><SafeMarkdown :content="item.content" /></div>
                  <span class="mistake-subline"
                    >{{ item.subject }} ·
                    {{ item.knowledge_tags.join('、') || '未标注知识点' }}</span
                  >
                </td>
                <td>
                  {{ item.exam_title
                  }}<span class="mistake-subline"
                    >第 {{ item.attempt_no }} 次 · {{ item.score }} / {{ item.full_score }} 分</span
                  >
                </td>
                <td>{{ questionTypeLabels[item.type] }}</td>
                <td>
                  <StatusBadge
                    :label="item.mastered ? '已掌握' : '待复习'"
                    :tone="item.mastered ? 'success' : 'neutral'"
                  />
                </td>
                <td><RouterLink :to="`/student/mistakes/${item.answer_id}`">复习 →</RouterLink></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="!loading && !data?.items.length" class="result-empty" role="status">
          {{
            loading ? '正在读取可见错题…' : failure ? '错题暂不可读取。' : '暂无符合条件的错题。'
          }}
        </p>
      </div>
      <ListPager
        v-if="data"
        label="错题记录"
        :page="page"
        :page-size="20"
        :total="data.total"
        :loading="loading"
        @change="page = $event"
      />
    </SurfacePanel>
    <p class="muted mistake-scope">
      仅显示已公布、允许回看且有效的作答；撤回结果或资格失效后，相关错题暂不可见。
    </p>
  </div>
</template>
<style scoped>
.mistake-filters {
  display: grid;
  grid-template-columns: minmax(180px, 1.6fr) repeat(4, minmax(110px, 1fr));
  align-items: end;
  gap: 14px;
  font-size: 13px;
}
.mistakes-panel :deep(.surface-panel-body) {
  padding: 0;
}
.mistakes-table {
  min-width: 850px;
}
.mistakes-table td:last-child a {
  display: inline-flex;
  border: 1px solid var(--neutral-400);
  padding: 9px 14px;
  color: var(--color-text);
  border-radius: 2px;
}
.mistakes-table th,
.mistakes-table td {
  padding: 18px 24px;
}
.mistakes-table td:first-child {
  width: 38%;
}
.mistakes-table td:nth-child(2) {
  width: 25%;
}
.mistake-content {
  max-height: 4.8em;
  overflow: hidden;
  line-height: 1.6;
  font-weight: 500;
}
.mistake-subline {
  display: block;
  color: var(--color-muted);
  font-size: 12px;
  margin-top: 7px;
  line-height: 1.7;
}
.mistakes-panel :deep(.list-pager) {
  padding: 16px 24px;
}
.filter-actions {
  display: flex;
  gap: 10px;
  grid-column: 1 / -1;
}
.mistake-scope {
  font-size: 12px;
  margin: 20px 0;
}
@media (max-width: 1100px) {
  .mistake-filters {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .mistake-filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .mistake-filters > label:first-child {
    grid-column: 1 / -1;
  }
}
</style>
