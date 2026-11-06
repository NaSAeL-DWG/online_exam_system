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
      title="我的错题"
      description="每次未满分作答分别保留；后次答对不会删除前次错误，掌握标记不改变成绩。"
    >
      <template #actions><NButton :loading="loading" @click="load">刷新错题</NButton></template>
    </PageHeader>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载错题</NButton></NAlert
    >
    <SurfacePanel>
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
      <p class="muted mistake-scope">
        仅显示已公布、允许回看且有效的作答；撤回结果或资格失效后，相关错题暂不可见。
      </p>
      <div class="result-list" :aria-busy="loading">
        <LoadingSkeleton v-if="loading" label="正在读取可见错题" />
        <article v-for="item in data?.items" :key="item.answer_id" class="mistake-row">
          <div class="mistake-row-meta">
            <span>{{ questionTypeLabels[item.type] }} · {{ item.subject }}</span
            ><StatusBadge :label="`${item.score} / ${item.full_score} 分`" tone="warning" />
          </div>
          <SafeMarkdown :content="item.content" />
          <div class="mistake-row-footer">
            <span class="muted"
              >{{ item.exam_title }} · 第 {{ item.attempt_no }} 次 ·
              {{ item.knowledge_tags.join('、') || '未标注知识点' }}</span
            ><StatusBadge
              :label="item.mastered ? '已掌握' : '待复习'"
              :tone="item.mastered ? 'success' : 'neutral'"
            /><RouterLink :to="`/student/mistakes/${item.answer_id}`">查看错题</RouterLink>
          </div>
        </article>
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
  </div>
</template>
<style scoped>
.mistake-filters {
  display: grid;
  grid-template-columns: minmax(180px, 1.5fr) repeat(4, minmax(110px, 1fr));
  align-items: end;
  gap: 14px;
  font-size: 13px;
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
.mistake-row {
  padding: 22px 0;
  border-top: 1px solid var(--color-border);
}
.mistake-row-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  font-size: 12px;
  color: var(--color-muted);
}
.mistake-row-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px;
  margin-top: 18px;
  font-size: 12px;
}
.mistake-row-footer > span:first-child {
  flex: 1;
  min-width: 150px;
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
  .mistake-filters label:first-child {
    grid-column: 1 / -1;
  }
  .mistake-filters > label:first-child {
    grid-column: 1 / -1;
  }
  .mistake-row-footer {
    gap: 12px;
  }
  .mistake-row-footer > span:first-child {
    flex-basis: 100%;
  }
}
</style>
