<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { NAlert, NButton, NDataTable, type DataTableColumns } from 'naive-ui'
import { questionsApi, questionTypeLabels, type Question } from '../api/questions'
import { errorMessage } from '../api/client'
import ListPager from './ListPager.vue'

const props = defineProps<{ excludedIds: string[] }>()
const emit = defineEmits<{ add: [question: Question] }>()
const query = ref('')
const filters = reactive({ subject: '', tag: '', difficulty: '', type: '' })
const page = ref(1)
const total = ref(0)
const items = ref<Question[]>([])
const loading = ref(false)
const failure = ref('')
const columns: DataTableColumns<Question> = [
  { title: '可用题目', key: 'content', ellipsis: { tooltip: true } },
  { title: '题型', key: 'type', render: (row) => questionTypeLabels[row.type] },
  { title: '科目', key: 'subject' },
  {
    title: '操作',
    key: 'actions',
    render: (row) =>
      h(
        NButton,
        {
          size: 'small',
          disabled: props.excludedIds.includes(row.id),
          onClick: () => emit('add', row),
        },
        { default: () => (props.excludedIds.includes(row.id) ? '已加入' : '加入') },
      ),
  },
]
let loadVersion = 0
async function load(): Promise<void> {
  const version = ++loadVersion
  loading.value = true
  failure.value = ''
  try {
    const result = await questionsApi.list(
      { page: page.value, page_size: 10, q: query.value },
      { ...filters, status: 'ACTIVE' },
    )
    if (version === loadVersion) {
      items.value = result.items
      total.value = result.total
    }
  } catch (error) {
    if (version === loadVersion) failure.value = errorMessage(error)
  } finally {
    if (version === loadVersion) loading.value = false
  }
}
function changePage(value: number): void {
  page.value = value
  void load()
}
onMounted(load)
</script>
<template>
  <section class="question-picker">
    <h3>从共享题库选题</h3>
    <div class="search-fields">
      <input
        v-model="query"
        aria-label="搜索可用题目"
        placeholder="搜索题干"
        @keyup.enter="changePage(1)"
      /><input v-model="filters.subject" aria-label="选题科目" placeholder="科目" /><input
        v-model="filters.tag"
        aria-label="选题知识点"
        placeholder="知识点"
      /><NButton @click="changePage(1)">查询可用题目</NButton>
    </div>
    <NAlert v-if="failure" type="error">{{ failure }}</NAlert>
    <NDataTable
      :columns="columns"
      :data="items"
      :loading="loading"
      :row-key="(row: Question) => row.id"
    />
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
.search-fields {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
input {
  min-width: 0;
  width: 100%;
  padding: 8px;
  border: 1px solid #d9dfe9;
  border-radius: 6px;
}
</style>
