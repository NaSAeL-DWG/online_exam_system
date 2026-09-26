<script setup lang="ts">
import { h, onMounted, ref } from 'vue'
import { NAlert, NButton, NCard, NDataTable, NModal, NSpace, type DataTableColumns } from 'naive-ui'
import { examParticipantsApi, type Participant } from '../api/examParticipants'
import { ApiError, errorMessage } from '../api/client'
import type { AudienceType, ExamStatus } from '../api/exams'
import type { TeachingClass } from '../types'
import MemberPicker from './MemberPicker.vue'
import ListPager from './ListPager.vue'

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
const classes = ref<TeachingClass[]>([])
const classQuery = ref('')
const classPage = ref(1)
const classTotal = ref(0)
const classLoading = ref(false)
const classFailure = ref('')
const selectedClassIds = ref<string[]>([])
const selectedStudentIds = ref<string[]>([])
const saving = ref(false)
const selected = ref<Participant | null>(null)
const action = ref<'cancel' | 'restore'>('cancel')
const reason = ref('')
const changeFailure = ref('')
const changeConflict = ref(false)
const changeVisible = ref(false)
const columns: DataTableColumns<Participant> = [
  {
    title: '学生',
    key: 'user',
    render: (row) => `${row.user.real_name}（${row.user.login_name}）`,
  },
  {
    title: '资格',
    key: 'status',
    render: (row) => (row.status === 'ASSIGNED' ? '有效资格' : '已撤销'),
  },
  { title: '已用次数', key: 'used_attempts' },
  { title: '废弃次数', key: 'voided_attempts' },
  { title: '撤销原因', key: 'cancelled_reason', render: (row) => row.cancelled_reason || '—' },
  {
    title: '操作',
    key: 'actions',
    render: (row) =>
      h(
        NButton,
        {
          size: 'small',
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
let classLoadVersion = 0
async function loadClasses(value = 1): Promise<void> {
  const version = ++classLoadVersion
  classPage.value = value
  classLoading.value = true
  classFailure.value = ''
  try {
    const result = await examParticipantsApi.classes({
      page: value,
      page_size: 10,
      q: classQuery.value,
    })
    if (version === classLoadVersion) {
      classes.value = result.items
      classTotal.value = result.total
    }
  } catch (error) {
    if (version === classLoadVersion) classFailure.value = errorMessage(error)
  } finally {
    if (version === classLoadVersion) classLoading.value = false
  }
}
async function add(): Promise<void> {
  if (saving.value) return
  saving.value = true
  failure.value = ''
  success.value = ''
  warning.value = ''
  try {
    const result = await examParticipantsApi.add(
      props.examId,
      selectedClassIds.value,
      selectedStudentIds.value,
    )
    selectedClassIds.value = []
    selectedStudentIds.value = []
    success.value = `新增 ${result.added} 人，已有 ${result.existing} 人`
    if (result.cancelled_user_ids.length)
      warning.value = `${result.cancelled_user_ids.length} 人的资格已撤销，需显式恢复。普通补入不会恢复资格。`
    await load()
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    saving.value = false
  }
}
function openChange(participant: Participant): void {
  selected.value = participant
  action.value = participant.status === 'ASSIGNED' ? 'cancel' : 'restore'
  reason.value = ''
  changeFailure.value = ''
  changeConflict.value = false
  changeVisible.value = true
}
async function change(): Promise<void> {
  if (!selected.value || saving.value) return
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
  void loadClasses()
})
</script>

<template>
  <NCard title="参考名单与资格">
    <NAlert v-if="audience === 'PUBLIC'" type="info"
      >公开考试面向全部已激活学生；名单仅显示已建立的资格。已撤销的资格不会因公开入口自动恢复。</NAlert
    >
    <p class="muted">
      按班级补入的是当前学生名单。之后班级成员变化不联动本场考试，跨班及单独选择自动去重。
    </p>
    <NAlert v-if="success" type="success">{{ success }}</NAlert
    ><NAlert v-if="warning" type="warning">{{ warning }}</NAlert
    ><NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重新加载名单</NButton></NAlert
    >
    <div v-if="status !== 'CANCELLED'" class="audience-pickers">
      <section>
        <h3>按教学班补入</h3>
        <NSpace
          ><input
            v-model="classQuery"
            aria-label="搜索补入班级"
            placeholder="搜索教学班"
            @keyup.enter="loadClasses()"
          /><NButton :loading="classLoading" @click="loadClasses()">查询补入班级</NButton></NSpace
        >
        <NAlert v-if="classFailure" type="error">{{ classFailure }}</NAlert>
        <div class="class-options">
          <label v-for="item in classes" :key="item.id"
            ><input
              v-model="selectedClassIds"
              type="checkbox"
              :value="item.id"
              :aria-label="`选择班级 ${item.name}`"
              :disabled="item.status === 'ARCHIVED' || saving"
            />{{ item.name }}（{{ item.student_count }} 人）</label
          >
        </div>
        <p>已选 {{ selectedClassIds.length }} 个班级（跨页保留）</p>
        <ListPager
          label="补入班级"
          :page="classPage"
          :page-size="10"
          :total="classTotal"
          :loading="classLoading"
          @change="loadClasses"
        />
      </section>
      <section>
        <h3>单独补入学生</h3>
        <MemberPicker v-model="selectedStudentIds" kind="student" />
      </section>
    </div>
    <NButton
      v-if="status !== 'CANCELLED'"
      type="primary"
      :loading="saving"
      :disabled="!selectedClassIds.length && !selectedStudentIds.length"
      @click="add"
      >补入参考名单</NButton
    >
    <div class="participant-search">
      <input
        v-model="query"
        aria-label="搜索参考名单"
        placeholder="学生姓名或学号"
        @keyup.enter="changePage(1)"
      /><select v-model="filter" aria-label="筛选资格">
        <option value="">全部资格</option>
        <option value="ASSIGNED">有效资格</option>
        <option value="CANCELLED">已撤销</option></select
      ><NButton @click="changePage(1)">查询参考名单</NButton>
    </div>
    <div data-testid="exam-participants">
      <NDataTable
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(row: Participant) => row.id"
      /><ListPager
        label="参考名单"
        :page="page"
        :page-size="20"
        :total="total"
        :loading="loading"
        @change="changePage"
      />
    </div>
    <NModal
      v-model:show="changeVisible"
      preset="card"
      :title="action === 'cancel' ? '撤销参考资格' : '显式恢复资格'"
      style="width: 600px"
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
      <form class="reason-form" @submit.prevent="change">
        <label
          >资格变更原因<textarea
            v-model="reason"
            aria-label="资格变更原因"
            required
            rows="3"
          /></label
        ><NButton attr-type="submit" type="primary" :loading="saving" :disabled="changeConflict">{{
          action === 'cancel' ? '确认撤销资格' : '确认恢复资格'
        }}</NButton>
      </form></NModal
    >
  </NCard>
</template>

<style scoped>
.audience-pickers {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin: 20px 0;
}
.class-options {
  display: grid;
  gap: 10px;
  margin-top: 18px;
}
.class-options label {
  display: flex;
  gap: 10px;
  align-items: center;
}
.class-options input {
  width: auto;
}
input,
select,
textarea {
  border: 1px solid #d9dfe9;
  border-radius: 6px;
  padding: 9px 12px;
  font: inherit;
}
.participant-search {
  display: flex;
  gap: 12px;
  margin: 24px 0 14px;
}
.reason-form {
  display: grid;
  gap: 18px;
  margin-top: 18px;
}
.reason-form label {
  display: grid;
  gap: 8px;
}
</style>
