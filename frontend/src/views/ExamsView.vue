<script setup lang="ts">
import { h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NAlert, NButton, NCard, NDataTable, NModal, NSpace, type DataTableColumns } from 'naive-ui'
import { examsApi, examStatusLabels, type AudienceType, type ExamSummary } from '../api/exams'
import { papersApi, type PaperSummary } from '../api/papers'
import { errorMessage } from '../api/client'
import ListPager from '../components/ListPager.vue'

const router = useRouter()
const items = ref<ExamSummary[]>([])
const page = ref(1)
const total = ref(0)
const query = ref('')
const failure = ref('')
const loading = ref(false)
const visible = ref(false)
const saving = ref(false)
const editorFailure = ref('')
const title = ref('')
const description = ref('')
const audience = ref<AudienceType>('RESTRICTED')
const paperId = ref('')
const papers = ref<PaperSummary[]>([])
const paperQuery = ref('')
const paperPage = ref(1)
const paperTotal = ref(0)
const paperLoading = ref(false)
const columns: DataTableColumns<ExamSummary> = [
  { title: '考试', key: 'title' },
  { title: '状态', key: 'status', render: (row) => examStatusLabels[row.status] },
  {
    title: '参考范围',
    key: 'audience_type',
    render: (row) => (row.audience_type === 'PUBLIC' ? '全部激活学生' : '限定名单'),
  },
  { title: '总分', key: 'total_score' },
  {
    title: '操作',
    key: 'actions',
    render: (row) =>
      h(
        NButton,
        { size: 'small', onClick: () => router.push(`/staff/exams/${row.id}`) },
        { default: () => '管理考试' },
      ),
  },
]
let loadVersion = 0
async function load(): Promise<void> {
  const version = ++loadVersion
  loading.value = true
  failure.value = ''
  try {
    const result = await examsApi.list({ page: page.value, page_size: 20, q: query.value })
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
async function loadPapers(value = 1): Promise<void> {
  paperLoading.value = true
  paperPage.value = value
  try {
    const result = await papersApi.list({ page: value, page_size: 20, q: paperQuery.value })
    papers.value = result.items
    paperTotal.value = result.total
  } catch (error) {
    editorFailure.value = errorMessage(error)
  } finally {
    paperLoading.value = false
  }
}
function create(): void {
  title.value = ''
  description.value = ''
  audience.value = 'RESTRICTED'
  paperId.value = ''
  paperQuery.value = ''
  editorFailure.value = ''
  visible.value = true
  void loadPapers()
}
async function save(): Promise<void> {
  if (saving.value) return
  saving.value = true
  editorFailure.value = ''
  try {
    const exam = await examsApi.create({
      source_paper_id: paperId.value,
      title: title.value,
      description: description.value || null,
      audience_type: audience.value,
    })
    visible.value = false
    await router.push(`/staff/exams/${exam.id}`)
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
        <p class="eyebrow accent">EXAMS</p>
        <h1>考试管理</h1>
        <p>创建即建立独立快照，发布前完成配置和参考名单。</p>
      </div>
      <NButton type="primary" @click="create">创建考试</NButton>
    </div>
    <NAlert v-if="failure" type="error">{{ failure }}</NAlert>
    <NCard
      ><NSpace
        ><input
          v-model="query"
          aria-label="搜索考试"
          placeholder="搜索考试名称"
          @keyup.enter="changePage(1)"
        /><NButton @click="changePage(1)">查询考试</NButton></NSpace
      ><NDataTable
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(row: ExamSummary) => row.id" /><ListPager
        label="考试"
        :page="page"
        :page-size="20"
        :total="total"
        :loading="loading"
        @change="changePage"
    /></NCard>
    <NModal
      v-model:show="visible"
      preset="card"
      title="创建考试"
      style="width: 700px"
      :mask-closable="false"
      :closable="!saving"
      :close-on-esc="!saving"
    >
      <NAlert v-if="editorFailure" type="error">{{ editorFailure }}</NAlert>
      <form class="exam-form" @submit.prevent="save">
        <label>考试名称<input v-model="title" aria-label="考试名称" required /></label
        ><label>考试说明<textarea v-model="description" aria-label="考试说明" rows="3" /></label
        ><label
          >参考范围<select v-model="audience" aria-label="参考范围">
            <option value="RESTRICTED">限定名单</option>
            <option value="PUBLIC">全部激活学生</option>
          </select></label
        >
        <NSpace
          ><input
            v-model="paperQuery"
            aria-label="搜索来源试卷"
            placeholder="搜索试卷"
            @keyup.enter.prevent="loadPapers()"
          /><NButton @click="loadPapers()">查询来源试卷</NButton></NSpace
        >
        <label
          >来源试卷<select v-model="paperId" aria-label="来源试卷" required>
            <option value="" disabled>选择当前页试卷</option>
            <option
              v-for="paper in papers"
              :key="paper.id"
              :value="paper.id"
              :disabled="paper.status === 'ARCHIVED'"
            >
              {{ paper.title }}{{ paper.status === 'ARCHIVED' ? '（已归档）' : '' }}
            </option>
          </select></label
        >
        <ListPager
          label="来源试卷"
          :page="paperPage"
          :page-size="20"
          :total="paperTotal"
          :loading="paperLoading"
          @change="loadPapers"
        />
        <NButton attr-type="submit" type="primary" :loading="saving">建立考试快照</NButton>
      </form>
    </NModal>
  </div>
</template>
<style scoped>
.exam-form {
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
