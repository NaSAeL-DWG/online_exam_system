<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NAlert, NButton, NModal } from 'naive-ui'
import { examsApi, examStatusLabels, type AudienceType } from '../api/exams'
import { errorMessage } from '../api/client'
import ListPager from '../components/ListPager.vue'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import SourcePaperPicker from '../features/exams/SourcePaperPicker.vue'
import { displayShanghaiTime } from '../features/exams/useExamDraft'
import { usePagedList } from '../composables/usePagedList'
const router = useRouter()
const { items, page, total, query, failure, loading, load, changePage } = usePagedList(
  examsApi.list,
)
const visible = ref(false)
const saving = ref(false)
const editorFailure = ref('')
const title = ref('')
const description = ref('')
const audience = ref<AudienceType>('RESTRICTED')
const paperId = ref('')
function create(): void {
  title.value = ''
  description.value = ''
  audience.value = 'RESTRICTED'
  paperId.value = ''
  editorFailure.value = ''
  visible.value = true
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
</script>
<template>
  <div class="page-stack">
    <PageHeader title="考试管理" description="从试卷创建考试，配置时间、评分与参考资格。"
      ><template #actions
        ><NButton type="primary" @click="create"
          ><template #icon><AppIcon name="plus" :size="17" /></template>创建考试</NButton
        ></template
      ></PageHeader
    >
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载考试</NButton></NAlert
    >
    <SurfacePanel
      ><form class="toolbar" @submit.prevent="changePage(1)">
        <input
          v-model="query"
          class="form-control exam-search"
          aria-label="搜索考试"
          placeholder="搜索考试名称"
        /><NButton attr-type="submit" :loading="loading">查询考试</NButton
        ><span class="toolbar-meta">共 {{ total }} 场考试</span>
      </form>
      <div class="table-region" :aria-busy="loading">
        <table class="exam-table">
          <thead>
            <tr>
              <th>考试名称</th>
              <th>状态</th>
              <th>参考范围</th>
              <th>总分</th>
              <th class="action-cell">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="exam in items" :key="exam.id">
              <td>
                <strong>{{ exam.title }}</strong>
                <p class="exam-time">
                  {{
                    exam.start_at
                      ? displayShanghaiTime(exam.start_at).replace('T', ' ')
                      : '尚未设置开始时间'
                  }}
                </p>
              </td>
              <td>
                <StatusBadge
                  :label="examStatusLabels[exam.status]"
                  :tone="
                    exam.status === 'DRAFT'
                      ? 'warning'
                      : exam.status === 'CANCELLED'
                        ? 'danger'
                        : 'success'
                  "
                />
              </td>
              <td>{{ exam.audience_type === 'PUBLIC' ? '全部激活学生' : '限定名单' }}</td>
              <td>
                <strong>{{ exam.total_score }}</strong
                ><span class="muted"> 分</span>
              </td>
              <td class="action-cell">
                <NButton size="small" @click="router.push(`/staff/exams/${exam.id}`)"
                  >管理考试</NButton
                >
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
      <form class="exam-create-form" @submit.prevent="save">
        <div class="form-grid two-columns">
          <label class="field"
            >考试名称<input
              v-model="title"
              aria-label="考试名称"
              required
              placeholder="例如：第一章单元测验" /></label
          ><label class="field"
            >参考范围<select v-model="audience" aria-label="参考范围">
              <option value="RESTRICTED">限定名单</option>
              <option value="PUBLIC">全部激活学生</option>
            </select></label
          ><label class="field full-width"
            >考试说明<textarea
              v-model="description"
              aria-label="考试说明"
              rows="2"
              placeholder="考试要求与作答说明（可选）"
            />
          </label>
        </div>
        <SourcePaperPicker v-if="visible" v-model="paperId" />
        <div class="editor-actions">
          <NButton attr-type="submit" type="primary" :loading="saving">建立考试快照</NButton>
        </div>
      </form></NModal
    >
  </div>
</template>
<style scoped>
.exam-search {
  flex: 1;
  min-width: 0;
  max-width: 420px;
}
.exam-table {
  width: 100%;
  min-width: 680px;
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
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}
td:first-child {
  width: 40%;
}
td strong {
  font-weight: 600;
}
.exam-time {
  margin: 6px 0 0;
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
