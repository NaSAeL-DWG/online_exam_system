<script setup lang="ts">
import { h, onMounted, ref } from 'vue'
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
import { papersApi, type Paper, type PaperSummary } from '../api/papers'
import type { Question } from '../api/questions'
import QuestionPicker from '../components/QuestionPicker.vue'
import SafeMarkdown from '../components/SafeMarkdown.vue'
import ListPager from '../components/ListPager.vue'

const dialog = useDialog()
const items = ref<PaperSummary[]>([])
const page = ref(1)
const total = ref(0)
const query = ref('')
const loading = ref(false)
const failure = ref('')
const visible = ref(false)
const saving = ref(false)
const editorFailure = ref('')
const conflict = ref(false)
const selected = ref<Paper | null>(null)
const title = ref('')
const description = ref('')
const questions = ref<{ question: Question; score: string }[]>([])
const columns: DataTableColumns<PaperSummary> = [
  { title: '试卷', key: 'title' },
  { title: '题数', key: 'question_count' },
  { title: '总分', key: 'total_score' },
  {
    title: '状态',
    key: 'status',
    render: (row) => (row.status === 'ACTIVE' ? '使用中' : '已归档'),
  },
  {
    title: '操作',
    key: 'actions',
    render: (row) =>
      h(NButton, { size: 'small', onClick: () => edit(row.id) }, { default: () => '编辑' }),
  },
]
let loadVersion = 0
async function load(): Promise<void> {
  const version = ++loadVersion
  loading.value = true
  failure.value = ''
  try {
    const result = await papersApi.list({ page: page.value, page_size: 20, q: query.value })
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
  title.value = ''
  description.value = ''
  questions.value = []
  editorFailure.value = ''
  conflict.value = false
  visible.value = true
}
async function edit(id: string): Promise<void> {
  try {
    const paper = await papersApi.get(id)
    selected.value = paper
    title.value = paper.title
    description.value = paper.description ?? ''
    questions.value = paper.questions.map((item) => ({
      question: item.question,
      score: item.score,
    }))
    editorFailure.value = ''
    conflict.value = false
    visible.value = true
  } catch (error) {
    failure.value = errorMessage(error)
  }
}
function move(index: number, direction: number): void {
  const item = questions.value.splice(index, 1)[0]
  if (item) questions.value.splice(index + direction, 0, item)
}
async function save(): Promise<void> {
  if (saving.value) return
  saving.value = true
  editorFailure.value = ''
  try {
    const input = {
      title: title.value,
      description: description.value || null,
      questions: questions.value.map((item) => ({
        question_id: item.question.id,
        score: String(item.score),
      })),
    }
    if (selected.value) await papersApi.update(selected.value.id, input, selected.value.version)
    else await papersApi.create(input)
    visible.value = false
    await load()
  } catch (error) {
    editorFailure.value = errorMessage(error)
    conflict.value = error instanceof ApiError && error.problem.code === 'VERSION_CONFLICT'
  } finally {
    saving.value = false
  }
}
function archive(): void {
  dialog.warning({
    title: '归档试卷',
    content: '归档后不能再用于创建新考试，已有考试快照保持不变。',
    positiveText: '确认归档',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await papersApi.archive(selected.value!.id, selected.value!.version)
        visible.value = false
        await load()
      } catch (error) {
        editorFailure.value = errorMessage(error)
        conflict.value = error instanceof ApiError && error.problem.code === 'VERSION_CONFLICT'
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
        <p class="eyebrow accent">SHARED PAPERS</p>
        <h1>共享试卷</h1>
        <p>手动选题、调整顺序与分值，供多场考试复用。</p>
      </div>
      <NButton type="primary" @click="create">新建试卷</NButton>
    </div>
    <NAlert v-if="failure" type="error">{{ failure }}</NAlert>
    <NCard
      ><NSpace
        ><input
          v-model="query"
          aria-label="搜索试卷"
          placeholder="搜索试卷名称"
          @keyup.enter="changePage(1)"
        /><NButton @click="changePage(1)">查询试卷</NButton></NSpace
      ><NDataTable
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(row: PaperSummary) => row.id" /><ListPager
        label="试卷"
        :page="page"
        :page-size="20"
        :total="total"
        :loading="loading"
        @change="changePage"
    /></NCard>
    <NModal
      v-model:show="visible"
      preset="card"
      :title="selected ? '编辑试卷' : '新建试卷'"
      style="width: 1000px; max-height: 90vh; overflow-y: auto"
      :mask-closable="false"
      :closable="!saving"
      :close-on-esc="!saving"
    >
      <NAlert v-if="editorFailure" type="error">{{ editorFailure }}</NAlert
      ><NButton v-if="conflict && selected" @click="edit(selected.id)">重新加载最新试卷</NButton>
      <NAlert v-if="selected?.status === 'ARCHIVED'" type="info"
        >此试卷已归档，保留内容供追溯。</NAlert
      >
      <form class="paper-form" @submit.prevent="save">
        <fieldset :disabled="saving || selected?.status === 'ARCHIVED'">
          <label>试卷名称<input v-model="title" aria-label="试卷名称" required /></label
          ><label>说明<textarea v-model="description" aria-label="试卷说明" rows="2" /></label>
        </fieldset>
        <section data-testid="selected-questions">
          <h3>已选题目（{{ questions.length }}）</h3>
          <article
            v-for="(item, index) in questions"
            :key="item.question.id"
            class="selected-question"
          >
            <div class="question-toolbar">
              <strong>第 {{ index + 1 }} 题</strong
              ><span v-if="item.question.status === 'CLOSED'">来源题已关闭；保留原关联</span
              ><label
                >分值<input
                  v-model="item.score"
                  :aria-label="`第 ${index + 1} 题分值`"
                  type="number"
                  min="0.1"
                  step="0.1"
                  required
                  :disabled="selected?.status === 'ARCHIVED'" /></label
              ><NButton
                :aria-label="`上移第 ${index + 1} 题`"
                :disabled="index === 0 || selected?.status === 'ARCHIVED'"
                @click="move(index, -1)"
                >上移</NButton
              ><NButton
                :disabled="index === questions.length - 1 || selected?.status === 'ARCHIVED'"
                @click="move(index, 1)"
                >下移</NButton
              ><NButton
                :disabled="selected?.status === 'ARCHIVED'"
                @click="questions.splice(index, 1)"
                >移出</NButton
              >
            </div>
            <SafeMarkdown :content="item.question.content" />
          </article>
        </section>
        <QuestionPicker
          v-if="selected?.status !== 'ARCHIVED'"
          :excluded-ids="questions.map((item) => item.question.id)"
          @add="questions.push({ question: $event, score: '1.0' })"
        />
        <NSpace v-if="selected?.status !== 'ARCHIVED'"
          ><NButton attr-type="submit" type="primary" :loading="saving" :disabled="conflict"
            >保存试卷</NButton
          ><NButton v-if="selected" type="warning" :disabled="conflict || saving" @click="archive"
            >归档试卷</NButton
          ></NSpace
        >
      </form>
    </NModal>
  </div>
</template>
<style scoped>
.paper-form {
  display: grid;
  gap: 20px;
}
fieldset {
  border: 0;
  padding: 0;
  display: grid;
  gap: 16px;
}
label {
  display: grid;
  gap: 7px;
}
input,
textarea {
  border: 1px solid #d9dfe9;
  border-radius: 6px;
  padding: 9px 12px;
  font: inherit;
}
.selected-question {
  border: 1px solid #e5eaf2;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 14px;
}
.question-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.question-toolbar label {
  display: flex;
  align-items: center;
  margin-left: auto;
}
.question-toolbar input {
  width: 90px;
}
</style>
