<script setup lang="ts">
import { h, onMounted, ref, useId } from 'vue'
import { NAlert, NButton, NDataTable, NModal, type DataTableColumns } from 'naive-ui'
import { examParticipantsApi, type Participant } from '../api/examParticipants'
import { ApiError, errorMessage } from '../api/client'
import type { AudienceType, ExamStatus } from '../api/exams'
import MemberPicker from './MemberPicker.vue'
import ListPager from './ListPager.vue'
import SurfacePanel from './ui/SurfacePanel.vue'
import StatusBadge from './ui/StatusBadge.vue'
import AppIcon from './ui/AppIcon.vue'
import ClassAudiencePicker from '../features/exams/ClassAudiencePicker.vue'
import {
  textError,
  useContentValidation,
  type ContentFieldErrors,
} from '../features/contentValidation'

const props = defineProps<{ examId: string; audience: AudienceType; status: ExamStatus }>()
const items = ref<Participant[]>([])
const page = ref(1)
const total = ref(0)
const query = ref('')
const filter = ref('')
const loading = ref(false)
const failure = ref('')
const success = ref('')
const warning = ref('')
const addVisible = ref(false)
const addFailure = ref('')
const selectedClassIds = ref<string[]>([])
const selectedStudentIds = ref<string[]>([])
const saving = ref(false)
const selected = ref<Participant | null>(null)
const action = ref<'cancel' | 'restore'>('cancel')
const reason = ref('')
const changeFailure = ref('')
const changeConflict = ref(false)
const changeVisible = ref(false)
const changeForm = ref<HTMLFormElement | null>(null)
const reasonErrorId = `${useId()}-qualification-error`
const { errors, validate, resetValidation } = useContentValidation((): ContentFieldErrors => {
  const issue = textError(reason.value, '资格变更原因', 2000, true)
  return issue ? { reason: issue } : {}
})
const columns: DataTableColumns<Participant> = [
  {
    title: '学生',
    key: 'user',
    width: 230,
    render: (row) =>
      h('div', [
        h('strong', { class: 'participant-name' }, row.user.real_name),
        h('span', { class: 'table-subtitle' }, row.user.login_name),
      ]),
  },
  {
    title: '资格',
    key: 'status',
    width: 120,
    render: (row) =>
      h(StatusBadge, {
        label: row.status === 'ASSIGNED' ? '有效资格' : '已撤销',
        tone: row.status === 'ASSIGNED' ? 'success' : 'danger',
      }),
  },
  { title: '已用次数', key: 'used_attempts', width: 100 },
  { title: '废弃次数', key: 'voided_attempts', width: 100 },
  {
    title: '撤销原因',
    key: 'cancelled_reason',
    width: 240,
    render: (row) => row.cancelled_reason || '—',
  },
  {
    title: '操作',
    key: 'actions',
    width: 110,
    render: (row) =>
      h(
        NButton,
        {
          size: 'small',
          secondary: true,
          type: row.status === 'ASSIGNED' ? 'error' : 'default',
          disabled: saving.value || props.status === 'CANCELLED',
          onClick: () => openChange(row),
        },
        { default: () => (row.status === 'ASSIGNED' ? '撤销资格' : '恢复资格') },
      ),
  },
]
let loadVersion = 0
async function load(): Promise<void> {
  const version = ++loadVersion
  loading.value = true
  failure.value = ''
  try {
    const result = await examParticipantsApi.list(
      props.examId,
      { page: page.value, page_size: 20, q: query.value },
      filter.value,
    )
    if (version === loadVersion) {
      items.value = result.items
      total.value = result.total
    }
  } catch (error) {
    if (version === loadVersion) failure.value = `名单未能加载：${errorMessage(error)}`
  } finally {
    if (version === loadVersion) loading.value = false
  }
}
function changePage(value: number): void {
  page.value = value
  void load()
}
async function add(): Promise<void> {
  if (saving.value) return
  if (selectedClassIds.value.length > 100 || selectedStudentIds.value.length > 1000) {
    addFailure.value = '每次最多选择 100 个教学班和 1000 位单独补入的学生，请分批补入。'
    return
  }
  saving.value = true
  addFailure.value = ''
  success.value = ''
  warning.value = ''
  try {
    const result = await examParticipantsApi.add(
      props.examId,
      selectedClassIds.value,
      selectedStudentIds.value,
    )
    // 清空本次选择但保留补入工具，便于继续操作；撤销资格只能走显式恢复。
    selectedClassIds.value = []
    selectedStudentIds.value = []
    success.value = `新增 ${result.added} 人，已有 ${result.existing} 人`
    if (result.cancelled_user_ids.length)
      warning.value = `${result.cancelled_user_ids.length} 人的资格已撤销，需显式恢复。普通补入不会恢复资格。`
    await load()
  } catch (error) {
    addFailure.value = errorMessage(error)
  } finally {
    saving.value = false
  }
}
function openChange(participant: Participant): void {
  resetValidation()
  selected.value = participant
  action.value = participant.status === 'ASSIGNED' ? 'cancel' : 'restore'
  reason.value = ''
  changeFailure.value = ''
  changeConflict.value = false
  changeVisible.value = true
}
async function change(): Promise<void> {
  if (!selected.value || saving.value || !validate(changeForm.value)) return
  saving.value = true
  changeFailure.value = ''
  success.value = ''
  try {
    await examParticipantsApi.change(props.examId, selected.value, action.value, reason.value)
    changeVisible.value = false
    warning.value = ''
    success.value =
      action.value === 'cancel'
        ? '资格已撤销，相关作答保留为废弃记录。'
        : '资格已恢复，历史作答和已用次数保持不变。'
    await load()
  } catch (error) {
    changeFailure.value = errorMessage(error)
    changeConflict.value = error instanceof ApiError && error.problem.code === 'VERSION_CONFLICT'
  } finally {
    saving.value = false
  }
}
async function reloadChange(): Promise<void> {
  changeVisible.value = false
  await load()
}
onMounted(() => {
  void load()
})
</script>

<template>
  <SurfacePanel title="参考名单与资格" description="查看学生的参考资格、已用次数与撤销记录。">
    <template #actions>
      <NButton
        v-if="status !== 'CANCELLED'"
        type="primary"
        :aria-expanded="addVisible"
        aria-controls="participant-add-tools"
        @click="addVisible = !addVisible"
      >
        <template #icon><AppIcon name="plus" :size="16" /></template>补入名单
      </NButton>
    </template>
    <div class="participant-workspace">
      <NAlert v-if="audience === 'PUBLIC'" type="info"
        >公开考试面向全部已激活学生；此处仅显示已建立的资格。已撤销的资格不会因公开入口自动恢复。</NAlert
      >
      <NAlert v-if="success" type="success">{{ success }}</NAlert>
      <NAlert v-if="warning" type="warning">{{ warning }}</NAlert>
      <NAlert v-if="failure" type="error"
        >{{ failure }} <NButton size="small" @click="load">重新加载名单</NButton></NAlert
      >
      <section
        v-if="addVisible && status !== 'CANCELLED'"
        id="participant-add-tools"
        class="participant-add-tools"
        aria-label="补入名单工具"
      >
        <div class="audience-pickers">
          <ClassAudiencePicker v-model="selectedClassIds" :disabled="saving" />
          <section class="student-audience-picker">
            <h3>单独补入学生</h3>
            <p class="muted">按姓名或学号找到需要单独补入的学生。</p>
            <MemberPicker v-model="selectedStudentIds" kind="student" :disabled="saving" />
          </section>
        </div>
        <NAlert v-if="addFailure" type="error">{{ addFailure }}</NAlert>
        <div class="add-actions">
          <p class="muted">班级后续成员变化不联动本场名单。已撤销资格需显式恢复。</p>
          <NButton
            type="primary"
            :loading="saving"
            :disabled="!selectedClassIds.length && !selectedStudentIds.length"
            @click="add"
            >补入参考名单</NButton
          >
        </div>
      </section>
      <div class="participant-search">
        <label class="field search-field"
          ><span>查找学生</span>
          <input
            v-model="query"
            aria-label="搜索参考名单"
            placeholder="学生姓名或学号"
            @keydown.enter.prevent="changePage(1)" /></label
        ><label class="field qualification-field"
          ><span>资格状态</span
          ><select v-model="filter" aria-label="筛选资格">
            <option value="">全部资格</option>
            <option value="ASSIGNED">有效资格</option>
            <option value="CANCELLED">已撤销</option>
          </select></label
        ><NButton :loading="loading" @click="changePage(1)">查询参考名单</NButton>
      </div>
      <div data-testid="exam-participants">
        <div class="table-region">
          <NDataTable
            :columns="columns"
            :data="items"
            :loading="loading"
            :bordered="false"
            :scroll-x="900"
            :row-key="(row: Participant) => row.id"
            ><template #empty
              ><div class="participants-empty">
                <AppIcon name="users" :size="28" /><strong>{{
                  query || filter ? '没有符合条件的学生' : '尚未建立参考资格'
                }}</strong>
                <p>
                  {{
                    query || filter
                      ? '调整搜索或资格状态后重试。'
                      : audience === 'PUBLIC'
                        ? '公开考试的学生首次进入答题流程时会建立资格。'
                        : '通过「补入名单」按教学班或学生建立参考资格。'
                  }}
                </p>
              </div></template
            ></NDataTable
          >
        </div>
        <ListPager
          label="参考名单"
          :page="page"
          :page-size="20"
          :total="total"
          :loading="loading"
          @change="changePage"
        />
      </div>
    </div>
    <NModal
      v-model:show="changeVisible"
      preset="card"
      :title="action === 'cancel' ? '撤销参考资格' : '显式恢复资格'"
      class="responsive-modal responsive-modal--compact"
      :mask-closable="false"
      :closable="!saving"
      :close-on-esc="!saving"
      ><NAlert type="warning">{{
        action === 'cancel'
          ? '将废弃该学生同场的全部作答，保留审计记录。'
          : '恢复资格不会复活旧作答，也不会重置已使用次数。'
      }}</NAlert
      ><NAlert v-if="changeFailure" type="error">{{ changeFailure }}</NAlert
      ><NButton v-if="changeConflict" @click="reloadChange">重新加载名单</NButton>
      <p v-if="selected" class="change-student">
        {{ selected.user.real_name }}<span class="muted">（{{ selected.user.login_name }}）</span>
      </p>
      <form ref="changeForm" class="reason-form" novalidate @submit.prevent="change">
        <label class="field"
          >资格变更原因<textarea
            v-model="reason"
            aria-label="资格变更原因"
            required
            maxlength="2000"
            rows="3"
            :aria-invalid="!!errors.reason"
            :aria-describedby="errors.reason ? reasonErrorId : undefined"
          />
          <span v-if="errors.reason" :id="reasonErrorId" class="field-error" role="alert">{{
            errors.reason
          }}</span>
        </label>
        <div class="editor-actions">
          <NButton :disabled="saving" @click="changeVisible = false">取消</NButton
          ><NButton
            attr-type="submit"
            :type="action === 'cancel' ? 'error' : 'primary'"
            :loading="saving"
            :disabled="changeConflict"
            >{{ action === 'cancel' ? '确认撤销资格' : '确认恢复资格' }}</NButton
          >
        </div>
      </form></NModal
    >
  </SurfacePanel>
</template>

<style scoped>
.field-error {
  color: #b42318;
  font-size: 12px;
}
.participant-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 20px;
  min-width: 0;
}
.participant-workspace > * {
  min-width: 0;
}
.participant-add-tools {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 18px;
  padding: 20px;
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  border-radius: var(--radius-sm);
}
.audience-pickers {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 28px;
}
.student-audience-picker {
  min-width: 0;
}
.student-audience-picker h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
}
.student-audience-picker > p {
  margin: 6px 0 16px;
  font-size: 12px;
}
.add-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  border-top: 1px solid var(--color-border);
  padding-top: 18px;
}
.add-actions p {
  margin: 0;
  font-size: 12px;
  max-width: 520px;
}
.add-actions .n-button {
  flex-shrink: 0;
}
.participant-search {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
}
.participant-search .field {
  font-size: 12px;
}
.search-field {
  flex: 1 1 240px;
  max-width: 440px;
}
.qualification-field {
  flex: 0 1 180px;
}
.participant-search > .n-button {
  margin-bottom: 3px;
}
.participants-empty {
  display: grid;
  justify-items: center;
  gap: 12px;
  padding: 30px 18px;
  color: var(--color-muted);
}
.participants-empty strong {
  font-size: 14px;
  color: var(--color-text);
  font-weight: 550;
}
.participants-empty p {
  margin: 0;
  font-size: 13px;
}
.change-student {
  margin: 20px 0 0;
  font-weight: 550;
}
.reason-form {
  display: grid;
  gap: 18px;
  margin-top: 18px;
}
:deep(.participant-name) {
  font-weight: 550;
}
@media (max-width: 1000px) {
  .audience-pickers {
    grid-template-columns: minmax(0, 1fr);
    gap: 24px;
  }
  .student-audience-picker {
    border-top: 1px solid var(--color-border);
    padding-top: 22px;
  }
}
@media (max-width: 600px) {
  .participant-add-tools {
    padding: 16px;
  }
  .add-actions {
    align-items: flex-start;
    flex-direction: column;
    gap: 14px;
  }
  .search-field,
  .qualification-field {
    flex-basis: 100%;
    max-width: none;
  }
}
</style>
