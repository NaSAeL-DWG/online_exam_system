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
import { errorMessage } from '../api/client'
import { identityApi } from '../api/identity'
import ListPager from '../components/ListPager.vue'
import type { StudentReview } from '../types'

const items = ref<StudentReview[]>([])
const loading = ref(false)
const failure = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const query = ref('')
let loadVersion = 0
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
  const version = ++loadVersion
  loading.value = true
  failure.value = ''
  try {
    const result = await identityApi.reviews({
      page: page.value,
      page_size: pageSize,
      q: query.value,
    })
    if (version !== loadVersion) return
    items.value = result.items
    total.value = result.total
  } catch (error) {
    if (version !== loadVersion) return
    items.value = []
    failure.value = errorMessage(error)
  } finally {
    if (version === loadVersion) loading.value = false
  }
}

function changePage(value: number): void {
  page.value = value
  void load()
}

async function decide(row: StudentReview, decision: 'APPROVED' | 'REJECTED'): Promise<void> {
  if (decision === 'REJECTED' && !reason.value.trim()) {
    message.warning('请填写拒绝原因')
    return
  }
  try {
    await identityApi.decideReview(
      row.id,
      decision,
      decision === 'REJECTED' ? reason.value.trim() : undefined,
    )
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
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重试加载</NButton></NAlert
    ><NCard :bordered="false"
      ><NSpace style="margin-bottom: 16px"
        ><NInput
          v-model:value="query"
          :input-props="{ 'aria-label': '搜索申请' }"
          placeholder="按姓名或学号搜索"
          @keyup.enter="changePage(1)"
        /><NButton :loading="loading" @click="changePage(1)">查询申请</NButton></NSpace
      ><NDataTable
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(row: StudentReview) => row.id" /><ListPager
        label="审核"
        :page="page"
        :page-size="pageSize"
        :total="total"
        :loading="loading"
        @change="changePage" /></NCard
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
