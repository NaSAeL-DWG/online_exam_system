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
  NTag,
  useDialog,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'
import { errorMessage, request } from '../api/client'
import { useAuthStore } from '../stores/auth'
import type { TeachingClass, UserSummary } from '../types'

const auth = useAuthStore()
const message = useMessage()
const dialog = useDialog()
const items = ref<TeachingClass[]>([])
const teachers = ref<UserSummary[]>([])
const students = ref<UserSummary[]>([])
const selected = ref<TeachingClass | null>(null)
const selectedStudentId = ref<string | null>(null)
const loading = ref(false)
const failure = ref('')
const editorVisible = ref(false)
const detailVisible = ref(false)
const editingId = ref<string | null>(null)
const form = reactive<{ name: string; description: string; teacher_ids: string[] }>({
  name: '',
  description: '',
  teacher_ids: [],
})
const isAdmin = computed(() => auth.user?.user_type === 'ADMIN')
const columns: DataTableColumns<TeachingClass> = [
  {
    title: '教学班',
    key: 'name',
    render: (row) =>
      h('div', [
        h('strong', row.name),
        h('small', { class: 'table-subtitle' }, row.description ?? '暂无说明'),
      ]),
  },
  {
    title: '负责教师',
    key: 'teachers',
    render: (row) => row.teachers.map((teacher) => teacher.real_name).join('、') || '未关联',
  },
  { title: '学生人数', key: 'student_count' },
  {
    title: '状态',
    key: 'status',
    render: (row) =>
      h(
        NTag,
        { type: row.status === 'ACTIVE' ? 'success' : 'default', round: true },
        { default: () => (row.status === 'ACTIVE' ? '使用中' : '已归档') },
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
            h(
              NButton,
              { size: 'small', onClick: () => openDetail(row) },
              { default: () => '成员管理' },
            ),
            isAdmin.value
              ? h(
                  NButton,
                  { size: 'small', onClick: () => openEdit(row) },
                  { default: () => '编辑' },
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
    const [classBody, studentBody] = await Promise.all([
      request<{ items: TeachingClass[]; total: number }>('/classes'),
      request<{ items: UserSummary[]; total: number }>('/staff/students'),
    ])
    items.value = classBody.items
    students.value = studentBody.items
    if (isAdmin.value)
      teachers.value = (
        await request<{ items: UserSummary[]; total: number }>('/admin/teachers')
      ).items
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}
function openCreate(): void {
  editingId.value = null
  Object.assign(form, { name: '', description: '', teacher_ids: [] })
  editorVisible.value = true
}
function openEdit(row: TeachingClass): void {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    description: row.description ?? '',
    teacher_ids: row.teachers.map((teacher) => teacher.id),
  })
  editorVisible.value = true
}
async function saveClass(): Promise<void> {
  try {
    const path = editingId.value ? `/classes/${editingId.value}` : '/classes'
    const method = editingId.value ? 'PATCH' : 'POST'
    await request(path, { method, body: JSON.stringify(form) })
    editorVisible.value = false
    message.success(editingId.value ? '教学班已更新' : '教学班已创建')
    await load()
  } catch (error) {
    message.error(errorMessage(error))
  }
}
async function openDetail(row: TeachingClass): Promise<void> {
  try {
    selected.value = (await request<{ class_info: TeachingClass }>(`/classes/${row.id}`)).class_info
    detailVisible.value = true
  } catch (error) {
    message.error(errorMessage(error))
  }
}
async function addStudent(): Promise<void> {
  if (!selected.value || !selectedStudentId.value) return
  try {
    selected.value = (
      await request<{ class_info: TeachingClass }>(
        `/classes/${selected.value.id}/members/${selectedStudentId.value}`,
        { method: 'PUT', body: JSON.stringify({ role: 'STUDENT' }) },
      )
    ).class_info
    selectedStudentId.value = null
    message.success('学生已加入教学班')
    await load()
  } catch (error) {
    message.error(errorMessage(error))
  }
}
function removeStudent(student: UserSummary): void {
  if (!selected.value) return
  dialog.warning({
    title: '移出学生',
    content: `确认将 ${student.real_name} 移出“${selected.value.name}”？已有考试名单不会随之变化。`,
    positiveText: '确认移出',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await request<void>(`/classes/${selected.value!.id}/members/${student.id}`, {
          method: 'DELETE',
        })
        await openDetail(selected.value!)
        await load()
        message.success('学生已移出')
      } catch (error) {
        message.error(errorMessage(error))
      }
    },
  })
}
function archive(row: TeachingClass): void {
  dialog.warning({
    title: '归档教学班',
    content: '归档后将不能继续维护成员，历史关系仍会保留。',
    positiveText: '确认归档',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await request(`/classes/${row.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ status: 'ARCHIVED' }),
        })
        message.success('教学班已归档')
        await load()
      } catch (error) {
        message.error(errorMessage(error))
      }
    },
  })
}
function archiveEditingClass(): void {
  const classInfo = items.value.find((item) => item.id === editingId.value)
  if (!classInfo) return
  editorVisible.value = false
  archive(classInfo)
}
const availableStudents = computed(() =>
  students.value
    .filter((student) => !selected.value?.students?.some((member) => member.id === student.id))
    .map((student) => ({
      label: `${student.real_name}（${student.login_name}）`,
      value: student.id,
    })),
)
onMounted(load)
</script>

<template>
  <div class="page-stack">
    <header class="page-title">
      <div>
        <p class="eyebrow accent">教学组织</p>
        <h1>教学班</h1>
        <p>一个教学班可关联多名教师，学生也可以加入多个教学班。</p>
      </div>
      <NButton v-if="isAdmin" type="primary" @click="openCreate">新建教学班</NButton>
    </header>
    <NAlert v-if="failure" type="error">{{ failure }}</NAlert
    ><NCard :bordered="false"
      ><NDataTable
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(row: TeachingClass) => row.id"
    /></NCard>
    <NModal
      v-model:show="editorVisible"
      preset="card"
      :title="editingId ? '编辑教学班' : '新建教学班'"
      style="width: 620px"
      ><NForm :model="form" label-placement="top"
        ><NFormItem label="教学班名称"
          ><NInput
            v-model:value="form.name"
            :input-props="{ 'aria-label': '教学班名称' }" /></NFormItem
        ><NFormItem label="说明"
          ><NInput
            v-model:value="form.description"
            :input-props="{ 'aria-label': '说明' }"
            type="textarea" /></NFormItem
        ><NFormItem label="负责教师"
          ><NSelect
            v-model:value="form.teacher_ids"
            aria-label="负责教师"
            multiple
            filterable
            :options="
              teachers.map((teacher) => ({
                label: `${teacher.real_name}（${teacher.login_name}）`,
                value: teacher.id,
              }))
            " /></NFormItem></NForm
      ><template #footer
        ><NSpace justify="space-between"
          ><NButton
            v-if="editingId && items.find((item) => item.id === editingId)?.status === 'ACTIVE'"
            type="warning"
            @click="archiveEditingClass"
            >归档教学班</NButton
          ><NSpace
            ><NButton @click="editorVisible = false">取消</NButton
            ><NButton type="primary" @click="saveClass">保存</NButton></NSpace
          ></NSpace
        ></template
      ></NModal
    >
    <NModal v-model:show="detailVisible" preset="card" :title="selected?.name" style="width: 760px"
      ><template v-if="selected"
        ><p class="muted">
          负责教师：{{
            selected.teachers.map((teacher) => teacher.real_name).join('、') || '未关联'
          }}
        </p>
        <NSpace v-if="selected.status === 'ACTIVE'" class="member-add"
          ><NSelect
            v-model:value="selectedStudentId"
            aria-label="选择学生"
            filterable
            placeholder="按姓名或学号选择已激活学生"
            :options="availableStudents"
            style="width: 420px"
          /><NButton type="primary" @click="addStudent">加入学生</NButton></NSpace
        ><NDataTable
          :columns="[
            { title: '学号', key: 'login_name' },
            { title: '姓名', key: 'real_name' },
            {
              title: '操作',
              key: 'actions',
              render: (row: UserSummary) =>
                h(
                  NButton,
                  {
                    size: 'small',
                    disabled: selected?.status !== 'ACTIVE',
                    onClick: () => removeStudent(row),
                  },
                  { default: () => '移出' },
                ),
            },
          ]"
          :data="selected.students ?? []" /></template
    ></NModal>
  </div>
</template>
