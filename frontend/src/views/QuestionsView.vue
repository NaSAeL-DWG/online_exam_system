<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NModal,
  NSpace,
  useDialog,
  type DataTableColumns,
} from 'naive-ui'
import { ApiError, errorMessage } from '../api/client'
import {
  questionsApi,
  questionTypeLabels,
  type Question,
  type QuestionInput,
} from '../api/questions'
import ListPager from '../components/ListPager.vue'
import QuestionFields from '../components/QuestionFields.vue'

const items = ref<Question[]>([])
const page = ref(1)
const total = ref(0)
const query = ref('')
const filters = reactive({ subject: '', difficulty: '', tag: '', status: '', type: '' })
const dialog = useDialog()
const conflict = ref(false)
const failure = ref('')
const editorFailure = ref('')
const loading = ref(false)
const saving = ref(false)
const uploading = ref(false)
const visible = ref(false)
const selected = ref<Question | null>(null)
const form = ref<QuestionInput>(blank())
function blank(): QuestionInput {
  return {
    type: 'TRUE_FALSE',
    content: '',
    options: [],
    standard_answer: true,
    explanation: null,
    subject: '',
    knowledge_tags: [],
    difficulty: 'MEDIUM',
  }
}
const columns: DataTableColumns<Question> = [
  { title: '题干', key: 'content', ellipsis: { tooltip: true } },
  { title: '题型', key: 'type', render: (row) => questionTypeLabels[row.type] },
  { title: '科目', key: 'subject' },
  {
    title: '状态',
    key: 'status',
    render: (row) => (row.status === 'ACTIVE' ? '使用中' : '已关闭'),
  },
  {
    title: '操作',
    key: 'actions',
    render: (row) =>
      h(NButton, { size: 'small', onClick: () => edit(row) }, { default: () => '编辑' }),
  },
]
let loadVersion = 0
async function load(): Promise<void> {
  const version = ++loadVersion
  loading.value = true
  failure.value = ''
  try {
    const result = await questionsApi.list(
      { page: page.value, page_size: 20, q: query.value },
      filters,
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
function create(): void {
  selected.value = null
  form.value = blank()
  editorFailure.value = ''
  conflict.value = false
  visible.value = true
}
async function edit(row: Question): Promise<void> {
  try {
    const question = await questionsApi.get(row.id)
    selected.value = question
    form.value = structuredClone(question)
    editorFailure.value = ''
    conflict.value = false
    visible.value = true
  } catch (error) {
    failure.value = errorMessage(error)
  }
}
async function save(): Promise<void> {
  saving.value = true
  editorFailure.value = ''
  try {
    const input = form.value
    if (selected.value) await questionsApi.update(selected.value.id, input, selected.value.version)
    else await questionsApi.create(input)
    visible.value = false
    await load()
  } catch (error) {
    editorFailure.value = errorMessage(error)
    conflict.value = error instanceof ApiError && error.status === 409
  } finally {
    saving.value = false
  }
}
function closeQuestion(): void {
  if (!selected.value) return
  dialog.warning({
    title: '关闭题目',
    content: '关闭后不能新增组卷，已有试卷和考试仍保留题目。',
    positiveText: '确认关闭',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await questionsApi.close(selected.value!.id, selected.value!.version)
        visible.value = false
        await load()
      } catch (error) {
        editorFailure.value = errorMessage(error)
        conflict.value = error instanceof ApiError && error.status === 409
      }
    },
  })
}
onMounted(load)
</script>

<template>
  <div class="page-stack">
    <div class="page-title">
      <div>
        <p class="eyebrow accent">QUESTION BANK</p>
        <h1>共享题库</h1>
        <p>全体教师共同维护，创建者仅用于追溯。</p>
      </div>
      <NButton type="primary" @click="create">新建题目</NButton>
    </div>
    <NAlert v-if="failure" type="error">{{ failure }}</NAlert>
    <NCard
      ><NSpace
        ><input
          v-model="query"
          aria-label="搜索题目"
          placeholder="搜索题干"
          @keyup.enter="changePage(1)"
        /><NButton @click="changePage(1)">查询题目</NButton></NSpace
      >
      <div class="filter-grid">
        <input v-model="filters.subject" aria-label="筛选科目" placeholder="科目" />
        <input v-model="filters.tag" aria-label="筛选知识点" placeholder="知识点标签" />
        <select v-model="filters.difficulty" aria-label="筛选难度">
          <option value="">全部难度</option>
          <option value="EASY">简单</option>
          <option value="MEDIUM">中等</option>
          <option value="HARD">困难</option>
        </select>
        <select v-model="filters.type" aria-label="筛选题型">
          <option value="">全部题型</option>
          <option v-for="(label, type) in questionTypeLabels" :key="type" :value="type">
            {{ label }}
          </option>
        </select>
        <select v-model="filters.status" aria-label="筛选状态">
          <option value="">全部状态</option>
          <option value="ACTIVE">使用中</option>
          <option value="CLOSED">已关闭</option>
        </select>
      </div>
      <NDataTable
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(row: Question) => row.id"
      />
      <ListPager
        label="题库"
        :page="page"
        :page-size="20"
        :total="total"
        :loading="loading"
        @change="changePage"
      />
    </NCard>
    <NModal
      v-model:show="visible"
      preset="card"
      :title="selected ? '编辑题目' : '新建题目'"
      style="width: 960px; max-height: 90vh; overflow-y: auto"
      :mask-closable="false"
    >
      <NAlert v-if="editorFailure" type="error">{{ editorFailure }}</NAlert>
      <NButton v-if="conflict && selected" @click="edit(selected)">重新加载最新题目</NButton>
      <form class="editor-form" @submit.prevent="save">
        <QuestionFields v-model="form" @uploading="uploading = $event" />
        <NSpace
          ><NButton
            attr-type="submit"
            type="primary"
            :loading="saving"
            :disabled="conflict || uploading"
            >保存题目</NButton
          ><NButton
            v-if="selected?.status === 'ACTIVE'"
            type="warning"
            :disabled="saving || conflict || uploading"
            @click="closeQuestion"
            >关闭题目</NButton
          ></NSpace
        >
      </form>
    </NModal>
  </div>
</template>

<style scoped>
.editor-form {
  display: grid;
  gap: 18px;
}
.filter-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin: 18px 0;
}
label {
  display: grid;
  gap: 7px;
}
input,
select,
textarea {
  border: 1px solid #d9dfe9;
  border-radius: 6px;
  padding: 9px 12px;
  font: inherit;
  width: 100%;
}
</style>
