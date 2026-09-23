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
  NSpace,
  NTag,
  useDialog,
  useMessage,
  type DataTableColumns,
} from 'naive-ui'
import { errorMessage } from '../api/client'
import { teachingClassesApi } from '../api/teachingClasses'
import ListPager from '../components/ListPager.vue'
import MemberPicker from '../components/MemberPicker.vue'
import { useAuthStore } from '../stores/auth'
import type { TeachingClass, UserSummary } from '../types'

const auth = useAuthStore()
const message = useMessage()
const dialog = useDialog()
const items = ref<TeachingClass[]>([])
const selectedTeachers = ref<UserSummary[]>([])
const selected = ref<TeachingClass | null>(null)
const selectedStudentIds = ref<string[]>([])
const loading = ref(false)
const failure = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const query = ref('')
let loadVersion = 0
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
  const version = ++loadVersion
  loading.value = true
  failure.value = ''
  try {
    const classBody = await teachingClassesApi.list({
      page: page.value,
      page_size: pageSize,
      q: query.value,
    })
    if (version !== loadVersion) return
    items.value = classBody.items
    total.value = classBody.total
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
function openCreate(): void {
  editingId.value = null
  selectedTeachers.value = []
  Object.assign(form, { name: '', description: '', teacher_ids: [] })
  editorVisible.value = true
}
function openEdit(row: TeachingClass): void {
  editingId.value = row.id
  selectedTeachers.value = row.teachers
  Object.assign(form, {
    name: row.name,
    description: row.description ?? '',
    teacher_ids: row.teachers.map((teacher) => teacher.id),
  })
  editorVisible.value = true
}
async function saveClass(): Promise<void> {
  try {
    if (editingId.value) await teachingClassesApi.update(editingId.value, form)
    else await teachingClassesApi.create(form)
    editorVisible.value = false
    message.success(editingId.value ? '教学班已更新' : '教学班已创建')
    await load()
  } catch (error) {
    message.error(errorMessage(error))
  }
}
async function openDetail(row: TeachingClass): Promise<void> {
  try {
    selected.value = (await teachingClassesApi.detail(row.id)).class_info
    selectedStudentIds.value = []
    detailVisible.value = true
  } catch (error) {
    message.error(errorMessage(error))
  }
}
async function addStudent(): Promise<void> {
  if (!selected.value || !selectedStudentIds.value[0]) return
  try {
    selected.value = (
      await teachingClassesApi.addStudent(selected.value.id, selectedStudentIds.value[0])
    ).class_info
    selectedStudentIds.value = []
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
        await teachingClassesApi.removeStudent(selected.value!.id, student.id)
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
        await teachingClassesApi.update(row.id, { status: 'ARCHIVED' })
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
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重试加载</NButton></NAlert
    ><NCard :bordered="false"
      ><NSpace style="margin-bottom: 16px"
        ><NInput
          v-model:value="query"
          :input-props="{ 'aria-label': '搜索教学班' }"
          placeholder="按名称或说明搜索"
          @keyup.enter="changePage(1)"
        /><NButton :loading="loading" @click="changePage(1)">查询教学班</NButton></NSpace
      ><NDataTable
        :columns="columns"
        :data="items"
        :loading="loading"
        :row-key="(row: TeachingClass) => row.id" /><ListPager
        label="教学班"
        :page="page"
        :page-size="pageSize"
        :total="total"
        :loading="loading"
        @change="changePage"
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
          ><MemberPicker
            v-if="editorVisible"
            v-model="form.teacher_ids"
            kind="teacher"
            :selected-members="selectedTeachers" /></NFormItem></NForm
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
        <div v-if="selected.status === 'ACTIVE'" class="member-add">
          <MemberPicker
            v-if="detailVisible"
            :key="selected.id"
            v-model="selectedStudentIds"
            kind="student"
            :excluded-ids="selected.students?.map((student) => student.id) ?? []"
          />
          <NButton
            type="primary"
            :disabled="!selectedStudentIds.length"
            style="margin-top: 12px"
            @click="addStudent"
            >加入学生</NButton
          >
        </div>
        <NDataTable
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
