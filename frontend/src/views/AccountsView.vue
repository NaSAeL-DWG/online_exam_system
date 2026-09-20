<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NTabPane,
  NTabs,
  NTag,
  useDialog,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'
import { errorMessage, request } from '../api/client'
import type { User, UserStatus } from '../types'

const users = ref<User[]>([])
const loading = ref(false)
const failure = ref('')
const createVisible = ref(false)
const editVisible = ref(false)
const resetVisible = ref(false)
const selected = ref<User | null>(null)
const message = useMessage()
const dialog = useDialog()
const teacher = reactive({
  teacher_no: '',
  real_name: '',
  email: '',
  phone_number: '',
  temporary_password: '',
})
const edit = reactive<{
  login_name: string
  real_name: string
  status: UserStatus
}>({ login_name: '', real_name: '', status: 'ACTIVATED' })
const temporaryPassword = ref('')
const statusOptions = computed(() => {
  if (selected.value?.status === 'WAITING_ACTIVATE') {
    return [
      { label: '待审核', value: 'WAITING_ACTIVATE', disabled: true },
      { label: '已停用', value: 'DEACTIVATED' },
    ]
  }
  return [
    { label: '已激活', value: 'ACTIVATED' },
    { label: '已停用', value: 'DEACTIVATED' },
  ]
})

const columns: DataTableColumns<User> = [
  { title: '账号', key: 'login_name' },
  { title: '姓名', key: 'real_name' },
  {
    title: '角色',
    key: 'user_type',
    render: (row) =>
      row.user_type === 'STUDENT' ? '学生' : row.user_type === 'TEACHER' ? '教师' : '管理员',
  },
  {
    title: '状态',
    key: 'status',
    render: (row) =>
      h(
        NTag,
        {
          type:
            row.status === 'ACTIVATED'
              ? 'success'
              : row.status === 'DEACTIVATED'
                ? 'error'
                : 'warning',
          round: true,
        },
        {
          default: () =>
            row.status === 'ACTIVATED'
              ? '已激活'
              : row.status === 'DEACTIVATED'
                ? '已停用'
                : '待审核',
        },
      ),
  },
  {
    title: '操作',
    key: 'actions',
    render: (row) =>
      h(
        NSpace,
        {},
        {
          default: () => [
            h(NButton, { size: 'small', onClick: () => openEdit(row) }, { default: () => '更正' }),
            row.user_type !== 'ADMIN'
              ? h(
                  NButton,
                  { size: 'small', onClick: () => openReset(row) },
                  { default: () => '重置密码' },
                )
              : null,
          ],
        },
      ),
  },
]

async function load(): Promise<void> {
  loading.value = true
  failure.value = ''
  try {
    users.value = (await request<{ items: User[]; total: number }>('/admin/users')).items
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}
async function createTeacher(): Promise<void> {
  try {
    await request('/admin/teachers', { method: 'POST', body: JSON.stringify(teacher) })
    createVisible.value = false
    Object.assign(teacher, {
      teacher_no: '',
      real_name: '',
      email: '',
      phone_number: '',
      temporary_password: '',
    })
    message.success('教师账号已创建')
    await load()
  } catch (error) {
    message.error(errorMessage(error))
  }
}
function openEdit(row: User): void {
  selected.value = row
  Object.assign(edit, {
    login_name: row.login_name,
    real_name: row.real_name,
    status: row.status,
  })
  editVisible.value = true
}
async function saveEdit(): Promise<void> {
  if (!selected.value) return
  try {
    const payload: { login_name: string; real_name: string; status?: 'ACTIVATED' | 'DEACTIVATED' } =
      {
        login_name: edit.login_name,
        real_name: edit.real_name,
      }
    // 待审核是审核流程产生的状态；仅在管理员明确停用或恢复时提交状态变更。
    if (edit.status !== selected.value.status && edit.status !== 'WAITING_ACTIVATE') {
      payload.status = edit.status
    }
    await request(`/admin/users/${selected.value.id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
    editVisible.value = false
    message.success('账号资料已更新')
    await load()
  } catch (error) {
    message.error(errorMessage(error))
  }
}
function openReset(row: User): void {
  selected.value = row
  temporaryPassword.value = ''
  resetVisible.value = true
}
async function resetPassword(): Promise<void> {
  if (!selected.value) return
  try {
    await request<void>(`/admin/users/${selected.value.id}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ temporary_password: temporaryPassword.value }),
    })
    resetVisible.value = false
    message.success('已重置密码并撤销旧会话')
  } catch (error) {
    message.error(errorMessage(error))
  }
}
function confirmStatus(): void {
  if (!selected.value) return
  dialog.warning({
    title:
      edit.status === selected.value.status
        ? '确认更正资料'
        : edit.status === 'DEACTIVATED'
          ? '确认停用账号'
          : '确认恢复账号',
    content:
      edit.status === selected.value.status
        ? '保存账号和姓名更正。'
        : edit.status === 'DEACTIVATED'
          ? '停用会立即撤销该账号的所有登录会话。'
          : '学生账号会依据最近审核结果恢复状态。',
    positiveText: '确认保存',
    negativeText: '取消',
    onPositiveClick: saveEdit,
  })
}
onMounted(load)
</script>

<template>
  <div class="page-stack">
    <header class="page-title">
      <div>
        <p class="eyebrow accent">系统管理</p>
        <h1>账号管理</h1>
        <p>创建教师，停用或恢复账号，更正姓名和登录账号。</p>
      </div>
      <NButton type="primary" @click="createVisible = true">新建教师</NButton>
    </header>
    <NAlert v-if="failure" type="error">{{ failure }}</NAlert
    ><NCard :bordered="false"
      ><NTabs type="line"
        ><NTabPane name="all" tab="全部账号"
          ><NDataTable
            :columns="columns"
            :data="users"
            :loading="loading"
            :row-key="(row: User) => row.id" /></NTabPane
        ><NTabPane name="teachers" tab="教师"
          ><NDataTable
            :columns="columns"
            :data="users.filter((user) => user.user_type === 'TEACHER')" /></NTabPane
        ><NTabPane name="students" tab="学生"
          ><NDataTable
            :columns="columns"
            :data="users.filter((user) => user.user_type === 'STUDENT')" /></NTabPane></NTabs
    ></NCard>
    <NModal v-model:show="createVisible" preset="card" title="新建教师账号" style="width: 640px"
      ><NForm :model="teacher" label-placement="top"
        ><div class="form-grid two-columns">
          <NFormItem label="工号"
            ><NInput
              v-model:value="teacher.teacher_no"
              :input-props="{ 'aria-label': '工号' }" /></NFormItem
          ><NFormItem label="姓名"
            ><NInput
              v-model:value="teacher.real_name"
              :input-props="{ 'aria-label': '姓名' }" /></NFormItem
          ><NFormItem label="邮箱"
            ><NInput
              v-model:value="teacher.email"
              :input-props="{ 'aria-label': '邮箱' }" /></NFormItem
          ><NFormItem label="手机号"
            ><NInput v-model:value="teacher.phone_number" :input-props="{ 'aria-label': '手机号' }"
          /></NFormItem>
        </div>
        <NFormItem label="临时密码"
          ><NInput
            v-model:value="teacher.temporary_password"
            :input-props="{ 'aria-label': '临时密码' }"
            type="password" /></NFormItem></NForm
      ><template #footer
        ><NSpace justify="end"
          ><NButton @click="createVisible = false">取消</NButton
          ><NButton type="primary" @click="createTeacher">创建教师</NButton></NSpace
        ></template
      ></NModal
    >
    <NModal v-model:show="editVisible" preset="card" title="更正账号资料" style="width: 520px"
      ><NForm :model="edit" label-placement="top"
        ><NFormItem label="登录账号"
          ><NInput
            v-model:value="edit.login_name"
            :input-props="{ 'aria-label': '登录账号' }" /></NFormItem
        ><NFormItem label="姓名"
          ><NInput
            v-model:value="edit.real_name"
            :input-props="{ 'aria-label': '姓名' }" /></NFormItem
        ><NFormItem label="账号状态"
          ><NSelect
            v-model:value="edit.status"
            aria-label="账号状态"
            :options="statusOptions" /></NFormItem></NForm
      ><template #footer
        ><NSpace justify="end"
          ><NButton @click="editVisible = false">取消</NButton
          ><NButton type="primary" @click="confirmStatus">保存更正</NButton></NSpace
        ></template
      ></NModal
    >
    <NModal v-model:show="resetVisible" preset="card" title="人工重置密码" style="width: 520px"
      ><NAlert type="warning">重置后旧会话立即失效，用户下次登录必须修改临时密码。</NAlert
      ><NFormItem label="新临时密码" class="modal-field"
        ><NInput
          v-model:value="temporaryPassword"
          :input-props="{ 'aria-label': '新临时密码' }"
          type="password" /></NFormItem
      ><template #footer
        ><NSpace justify="end"
          ><NButton @click="resetVisible = false">取消</NButton
          ><NButton type="warning" @click="resetPassword">确认重置</NButton></NSpace
        ></template
      ></NModal
    >
  </div>
</template>
