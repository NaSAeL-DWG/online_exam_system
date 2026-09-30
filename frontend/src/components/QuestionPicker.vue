<script setup lang="ts">
import { reactive } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import { questionsApi, questionTypeLabels, type Question } from '../api/questions'
import ListPager from './ListPager.vue'
import StatusBadge from './ui/StatusBadge.vue'
import { usePagedList } from '../composables/usePagedList'
import { difficultyLabels, questionSummary } from '../features/questions/questionDraft'
const props = defineProps<{ excludedIds: string[] }>()
const emit = defineEmits<{ add: [question: Question] }>()
const filters = reactive({ subject: '', tag: '', difficulty: '', type: '' })
const { query, page, total, items, loading, failure, load, changePage } = usePagedList(
  (query) => questionsApi.list(query, { ...filters, status: 'ACTIVE' }),
  10,
)
</script>
<template>
  <section class="question-picker" aria-label="从共享题库选题">
    <header class="picker-heading">
      <h3>从共享题库选题</h3>
      <p class="muted">仅展示可新增使用的题目。</p>
    </header>
    <div class="picker-search">
      <input
        class="form-control"
        v-model="query"
        aria-label="搜索可用题目"
        placeholder="搜索题干"
        @keydown.enter.prevent="changePage(1)"
      /><NButton :loading="loading" @click="changePage(1)">查询可用题目</NButton>
    </div>
    <div class="picker-filters">
      <input
        class="form-control"
        v-model="filters.subject"
        aria-label="选题科目"
        placeholder="科目"
      /><input
        class="form-control"
        v-model="filters.tag"
        aria-label="选题知识点"
        placeholder="知识点"
      /><select class="form-control" v-model="filters.difficulty" aria-label="选题难度">
        <option value="">全部难度</option>
        <option v-for="(label, value) in difficultyLabels" :key="value" :value="value">
          {{ label }}
        </option></select
      ><select class="form-control" v-model="filters.type" aria-label="选题题型">
        <option value="">全部题型</option>
        <option v-for="(label, type) in questionTypeLabels" :key="type" :value="type">
          {{ label }}
        </option>
      </select>
    </div>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重试加载题目</NButton></NAlert
    >
    <div class="table-region" :aria-busy="loading">
      <table class="picker-table">
        <thead>
          <tr>
            <th>可用题目</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td>
              <p class="question-summary">{{ questionSummary(item.content) }}</p>
              <div class="question-meta">
                <StatusBadge :label="questionTypeLabels[item.type]" /><span
                  >{{ item.subject }} · {{ difficultyLabels[item.difficulty] }}</span
                >
              </div>
            </td>
            <td>
              <NButton
                size="small"
                :type="excludedIds.includes(item.id) ? 'default' : 'primary'"
                :secondary="!excludedIds.includes(item.id)"
                :disabled="excludedIds.includes(item.id)"
                @click="emit('add', item)"
                >{{ excludedIds.includes(item.id) ? '已加入' : '加入' }}</NButton
              >
            </td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="2" class="picker-empty">
              {{ loading ? '正在加载…' : '没有找到可用题目，请调整筛选。' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <ListPager
      label="可用题目"
      :page="page"
      :page-size="10"
      :total="total"
      :loading="loading"
      @change="changePage"
    />
  </section>
</template>
<style scoped>
.question-picker {
  min-width: 0;
}
.picker-heading h3,
.picker-heading p {
  margin: 0;
}
.picker-heading h3 {
  font-size: 15px;
}
.picker-heading p {
  font-size: 12px;
  margin-top: 4px;
  margin-bottom: 16px;
}
.picker-search {
  display: flex;
  gap: 8px;
}
.picker-search input {
  flex: 1;
  min-width: 0;
}
.picker-filters {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 10px 0 16px;
}
.picker-table {
  width: 100%;
  min-width: 310px;
  border-collapse: collapse;
  text-align: left;
}
.table-region {
  max-height: 310px;
}
th {
  background: var(--color-bg);
  font-size: 12px;
  font-weight: 500;
  color: var(--color-muted);
}
th,
td {
  padding: 12px 10px;
  border-bottom: 1px solid var(--color-border);
}
th:last-child,
td:last-child {
  text-align: right;
  white-space: nowrap;
}
.question-summary {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  overflow-wrap: anywhere;
}
.question-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: var(--color-muted);
}
.picker-empty {
  padding: 32px 8px;
  text-align: center;
  color: var(--color-muted);
  font-size: 13px;
}
@media (max-width: 480px) {
  .picker-search {
    flex-wrap: wrap;
  }
  .picker-search input {
    flex-basis: 100%;
  }
}
</style>
