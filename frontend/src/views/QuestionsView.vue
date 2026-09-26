<script setup lang="ts">
import { h, onMounted, ref } from 'vue'
import { NAlert, NButton, NCard, NDataTable, NModal, NSpace, type DataTableColumns } from 'naive-ui'
import { errorMessage } from '../api/client'
import {
  questionsApi,
  questionTypeLabels,
  type Question,
  type QuestionInput,
} from '../api/questions'
import ListPager from '../components/ListPager.vue'

const items = ref<Question[]>([])
const page = ref(1)
const total = ref(0)
const query = ref('')
const failure = ref('')
const editorFailure = ref('')
const loading = ref(false)
const saving = ref(false)
const visible = ref(false)
const selected = ref<Question | null>(null)
const form = ref<QuestionInput>(blank())
const answer = ref('true')
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
    const result = await questionsApi.list({ page: page.value, page_size: 20, q: query.value })
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
  answer.value = 'true'
  editorFailure.value = ''
  visible.value = true
}
async function edit(row: Question): Promise<void> {
  try {
    const question = await questionsApi.get(row.id)
    selected.value = question
    form.value = structuredClone(question)
    answer.value = String(question.standard_answer)
    editorFailure.value = ''
    visible.value = true
  } catch (error) {
    failure.value = errorMessage(error)
  }
}
async function save(): Promise<void> {
  saving.value = true
  editorFailure.value = ''
  try {
    const input = { ...form.value, standard_answer: answer.value === 'true' }
    if (selected.value) await questionsApi.update(selected.value.id, input, selected.value.version)
    else await questionsApi.create(input)
    visible.value = false
    await load()
  } catch (error) {
    editorFailure.value = errorMessage(error)
  } finally {
    saving.value = false
  }
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
      style="width: 800px"
      :mask-closable="false"
    >
      <NAlert v-if="editorFailure" type="error">{{ editorFailure }}</NAlert>
      <form class="editor-form" @submit.prevent="save">
        <label
          >题型<select v-model="form.type" aria-label="题型">
            <option value="TRUE_FALSE">判断题</option>
          </select></label
        >
        <label>科目<input v-model="form.subject" aria-label="科目" required /></label>
        <label>题干<textarea v-model="form.content" aria-label="题干" required rows="6" /></label>
        <label
          >判断答案<select v-model="answer" aria-label="判断答案">
            <option value="true">真</option>
            <option value="false">假</option>
          </select></label
        >
        <NButton attr-type="submit" type="primary" :loading="saving">保存题目</NButton>
      </form>
    </NModal>
  </div>
</template>

<style scoped>
.editor-form {
  display: grid;
  gap: 18px;
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
