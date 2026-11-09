<script setup lang="ts">
import { onMounted, ref, useId } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton, NModal } from 'naive-ui'
import NSelect from '../components/ui/AppSelect.vue'
import { examsApi, examStatusLabels, type AudienceType, type ExamStatus } from '../api/exams'
import { errorMessage } from '../api/client'
import ListPager from '../components/ListPager.vue'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import SourcePaperPicker from '../features/exams/SourcePaperPicker.vue'
import { displayShanghaiTime } from '../features/exams/useExamDraft'
import { usePagedList } from '../composables/usePagedList'
import {
  textError,
  useContentValidation,
  type ContentFieldErrors,
} from '../features/contentValidation'
const router = useRouter()
const route = useRoute()
const status = ref<ExamStatus | ''>('')
const { items, page, total, query, failure, loading, load, changePage } = usePagedList((query) =>
  examsApi.list({ ...query, status: status.value || undefined }),
)
const visible = ref(false)
const saving = ref(false)
const editorFailure = ref('')
const title = ref('')
const description = ref('')
const audience = ref<AudienceType>('RESTRICTED')
const paperId = ref('')
const formRoot = ref<HTMLFormElement | null>(null)
const errorPrefix = useId()
const { errors, validate, resetValidation } = useContentValidation(() => {
  const errors: ContentFieldErrors = {}
  const titleIssue = textError(title.value, '考试名称', 200, true)
  const descriptionIssue = textError(description.value, '考试说明', 100000)
  if (titleIssue) errors.title = titleIssue
  if (descriptionIssue) errors.description = descriptionIssue
  if (!paperId.value) errors.source_paper_id = '请选择来源试卷。'
  return errors
})
function create(): void {
  resetValidation()
  title.value = ''
  description.value = ''
  audience.value = 'RESTRICTED'
  paperId.value = ''
  editorFailure.value = ''
  visible.value = true
}
async function save(): Promise<void> {
  if (saving.value || !validate(formRoot.value)) return
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
onMounted(() => {
  // 工作台的创建入口打开同一套来源试卷选择流程。
  if (route.query.create === '1') create()
})
</script>
<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="STAFF / EXAMS"
      title="考试管理"
      description="从草稿配置到结果公布，按考试阶段管理每一次测验。"
      ><template #actions
        ><NButton type="primary" @click="create"
          ><template #icon><AppIcon name="plus" :size="17" /></template>创建考试</NButton
        ></template
      ></PageHeader
    >
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载考试</NButton></NAlert
    >
    <form class="toolbar exam-list-filter" @submit.prevent="changePage(1)">
      <input
        v-model="query"
        class="form-control exam-search"
        aria-label="搜索考试"
        placeholder="搜索考试名称"
      /><NSelect
        v-model:value="status"
        class="exam-status-filter"
        aria-label="考试状态"
        :options="[
          { label: '全部状态', value: '' },
          ...Object.entries(examStatusLabels).map(([value, label]) => ({ value, label })),
        ]"
        @update:value="changePage(1)"
      /><NButton attr-type="submit" :loading="loading">查询考试</NButton
      ><span class="toolbar-meta">共 {{ total }} 场考试</span>
    </form>
    <SurfacePanel class="exam-list-panel">
      <LoadingSkeleton v-if="loading && !items.length" variant="table" label="正在加载考试" />
      <div v-else class="table-region" :aria-busy="loading">
        <table class="exam-table">
          <thead>
            <tr>
              <th>考试名称</th>
              <th>时间与范围</th>
              <th>试卷与作答</th>
              <th>状态</th>
              <th class="action-cell">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="exam in items" :key="exam.id">
              <td>
                <strong>{{ exam.title }}</strong>
                <p class="exam-id">{{ exam.id }}</p>
              </td>
              <td>
                <p class="exam-time">
                  {{
                    exam.start_at
                      ? displayShanghaiTime(exam.start_at).replace('T', ' ')
                      : '尚未设置开始时间'
                  }}
                  <template v-if="exam.end_at">
                    — {{ displayShanghaiTime(exam.end_at).replace('T', ' ') }}</template
                  >
                </p>
                <span class="exam-scope">{{
                  exam.audience_type === 'PUBLIC' ? '全部激活学生' : '限定名单'
                }}</span>
              </td>
              <td>
                <strong>{{ exam.total_score }}</strong
                ><span class="muted"> 分</span>
                <p class="exam-time">最多作答 {{ exam.max_attempts }} 次</p>
              </td>
              <td>
                <StatusBadge
                  :label="examStatusLabels[exam.status]"
                  :tone="
                    exam.status === 'DRAFT'
                      ? 'warning'
                      : exam.status === 'CANCELLED'
                        ? 'danger'
                        : exam.status === 'RESULTS_PUBLISHED'
                          ? 'success'
                          : 'info'
                  "
                />
              </td>
              <td class="action-cell">
                <NButton size="small" @click="router.push(`/staff/exams/${exam.id}`)">{{
                  exam.status === 'DRAFT' ? '配置考试' : '管理考试'
                }}</NButton>
              </td>
            </tr>
            <tr v-if="!items.length">
              <td colspan="5" class="empty-state">
                {{ loading ? '正在加载考试…' : '没有找到考试，可调整搜索或创建考试。' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <ListPager
        label="考试"
        :page="page"
        :page-size="20"
        :total="total"
        :loading="loading"
        @change="changePage"
    /></SurfacePanel>
    <NModal
      v-model:show="visible"
      preset="card"
      title="创建考试"
      class="responsive-modal responsive-modal--wide"
      :mask-closable="false"
      :closable="!saving"
      :close-on-esc="!saving"
      ><NAlert v-if="editorFailure" class="form-alert" type="error">{{ editorFailure }}</NAlert>
      <form ref="formRoot" class="exam-create-form" novalidate @submit.prevent="save">
        <div class="form-grid two-columns">
          <label class="field"
            >考试名称<input
              v-model="title"
              aria-label="考试名称"
              required
              maxlength="200"
              :aria-invalid="!!errors.title"
              :aria-describedby="errors.title ? `${errorPrefix}-title-error` : undefined"
              placeholder="例如：第一章单元测验"
            /><span
              v-if="errors.title"
              :id="`${errorPrefix}-title-error`"
              class="field-error"
              role="alert"
              >{{ errors.title }}</span
            ></label
          ><label class="field"
            >参考范围<NSelect
              v-model:value="audience"
              aria-label="参考范围"
              :options="[
                { value: 'RESTRICTED', label: '限定名单' },
                { value: 'PUBLIC', label: '全部激活学生' },
              ]" /></label
          ><label class="field full-width"
            >考试说明<textarea
              v-model="description"
              aria-label="考试说明"
              rows="2"
              maxlength="100000"
              :aria-invalid="!!errors.description"
              :aria-describedby="
                errors.description ? `${errorPrefix}-description-error` : undefined
              "
              placeholder="考试要求与作答说明（可选）"
            />
            <span
              v-if="errors.description"
              :id="`${errorPrefix}-description-error`"
              class="field-error"
              role="alert"
              >{{ errors.description }}</span
            >
          </label>
        </div>
        <SourcePaperPicker v-if="visible" v-model="paperId" :error="errors.source_paper_id" />
        <div class="editor-actions">
          <NButton attr-type="submit" type="primary" :loading="saving">建立考试快照</NButton>
        </div>
      </form></NModal
    >
  </div>
</template>
<style scoped>
.field-error {
  color: var(--red-600);
  font-size: 12px;
}
.exam-search {
  flex: 0 1 360px;
  min-width: 0;
  max-width: 360px;
}
.exam-list-filter {
  margin: 0;
  padding: 0;
}
.exam-status-filter {
  width: 160px;
}
.exam-list-panel :deep(.surface-panel-body) {
  padding: 0;
}
.exam-list-panel :deep(.list-pager) {
  padding: 16px 20px;
}
.exam-id {
  max-width: 280px;
  overflow-wrap: anywhere;
  margin: 7px 0 0;
  color: var(--color-muted);
  font:
    10px Consolas,
    monospace;
}
.exam-scope {
  display: block;
  margin-top: 7px;
  color: var(--color-muted);
  font-size: 11px;
}
.exam-table {
  width: 100%;
  min-width: 820px;
  border-collapse: collapse;
  text-align: left;
}
th {
  background: var(--color-bg);
  color: var(--color-muted);
  font-size: 12px;
  font-weight: 500;
}
th,
td {
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border);
}
td:first-child {
  width: 30%;
}
td strong {
  font-weight: 600;
}
.exam-time {
  margin: 0;
  color: var(--color-muted);
  font-size: 12px;
}
.action-cell {
  text-align: right;
  white-space: nowrap;
}
.empty-state {
  text-align: center;
  color: var(--color-muted);
  padding: 48px 16px;
}
.exam-create-form {
  display: grid;
  gap: 22px;
}
.form-grid {
  gap: 18px;
}
.full-width {
  grid-column: 1 / -1;
}
@media (max-width: 600px) {
  .exam-search {
    flex-basis: 100%;
    max-width: none;
  }
}
</style>
