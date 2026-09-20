<script setup lang="ts">
import { h, onMounted, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NInput,
  NModal,
  NSpace,
  NTag,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'
import { errorMessage, request } from '../api/client'
import type { StudentReview } from '../types'

const items = ref<StudentReview[]>([])
const loading = ref(false)
const failure = ref('')
const selected = ref<StudentReview | null>(null)
const rejectVisible = ref(false)
const reason = ref('')
const message = useMessage()

const columns: DataTableColumns<StudentReview> = [
  { title: '学号', key: 'student_no', render: (row) => row.submitted_profile.student_no },
  { title: '姓名', key: 'real_name', render: (row) => row.submitted_profile.real_name },
  {
    title: '联系方式',
    key: 'contact',
    render: (row) =>
      h('div', [
        h('div', row.submitted_profile.email),
        h('small', row.submitted_profile.phone_number),
      ]),
  },
  {
    title: '提交时间',
    key: 'submitted_at',
    render: (row) => new Date(row.submitted_at).toLocaleString('zh-CN'),
  },
  {
    title: '状态',
    key: 'status',
    render: (row) =>
      h(
        NTag,
        {
          type:
            row.status === 'PENDING' ? 'warning' : row.status === 'APPROVED' ? 'success' : 'error',
          round: true,
        },
        {
          default: () =>
            row.status === 'PENDING' ? '待审核' : row.status === 'APPROVED' ? '已通过' : '已拒绝',
        },
      ),
  },
  {
    title: '操作',
    key: 'actions',
    render: (row) =>
      row.status === 'PENDING'
        ? h(
            NSpace,
            {},
            {
              default: () => [
                h(
                  NButton,
                  { size: 'small', type: 'primary', onClick: () => decide(row, 'APPROVED') },
                  { default: () => '通过' },
                ),
                h(
                  NButton,
                  { size: 'small', onClick: () => openReject(row) },
                  { default: () => '拒绝' },
                ),
              ],
            },
          )
        : '—',
  },
]

async function load(): Promise<void> {
  loading.value = true
  failure.value = ''
  try {
    items.value = (await request<{ items: StudentReview[]; total: number }>('/staff/reviews')).items
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}

async function decide(row: StudentReview, decision: 'APPROVED' | 'REJECTED'): Promise<void> {
  if (decision === 'REJECTED' && !reason.value.trim()) {
    message.warning('请填写拒绝原因')
    return
  }
  try {
    await request(`/staff/reviews/${row.id}/decision`, {
      method: 'POST',
      body: JSON.stringify({
        decision,
        ...(decision === 'REJECTED' ? { reason: reason.value.trim() } : {}),
      }),
    })
    message.success(decision === 'APPROVED' ? '已通过学生申请' : '已拒绝学生申请')
    rejectVisible.value = false
    reason.value = ''
    await load()
  } catch (error) {
    message.error(errorMessage(error))
  }
}
function openReject(row: StudentReview): void {
  selected.value = row
  reason.value = ''
  rejectVisible.value = true
}
onMounted(load)
</script>

<template>
  <div class="page-stack">
    <header class="page-title">
      <div>
        <p class="eyebrow accent">身份管理</p>
        <h1>学生注册审核</h1>
        <p>核对学号、姓名和联系方式，拒绝时必须说明原因。</p>
      </div>
      <NButton @click="load">刷新</NButton>
    </header>
    <NAlert v-if="failure" type="error">{{ failure }}</NAlert
    ><NCard :bordered="false"
      ><NDataTable
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(row: StudentReview) => row.id" /></NCard
    ><NModal v-model:show="rejectVisible" preset="card" title="拒绝学生申请" style="width: 520px"
      ><p>
        学生：{{ selected?.submitted_profile.real_name }}（{{
          selected?.submitted_profile.student_no
        }}）
      </p>
      <NInput
        v-model:value="reason"
        type="textarea"
        :input-props="{ 'aria-label': '拒绝原因' }"
        placeholder="说明资料中需要更正的内容"
        :autosize="{ minRows: 3 }"
      /><template #footer
        ><NSpace justify="end"
          ><NButton @click="rejectVisible = false">取消</NButton
          ><NButton type="error" @click="selected && decide(selected, 'REJECTED')"
            >确认拒绝</NButton
          ></NSpace
        ></template
      ></NModal
    >
  </div>
</template>
