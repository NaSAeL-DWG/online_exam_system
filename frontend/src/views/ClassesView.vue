<script setup lang="ts">
import { h } from 'vue'
import {
  NAlert,
  NButton,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSpace,
  type DataTableColumns,
} from 'naive-ui'
import ListPager from '../components/ListPager.vue'
import MemberPicker from '../components/MemberPicker.vue'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import FormField from '../components/ui/FormField.vue'
import { useTeachingClassDirectory } from '../features/classes/useTeachingClassDirectory'
import type { TeachingClass, UserSummary } from '../types'

const {
  items,
  selectedTeachers,
  selected,
  selectedStudentIds,
  loading,
  saving,
  failure,
  page,
  pageSize,
  total,
  query,
  editorVisible,
  detailVisible,
  editingId,
  editingClass,
  form,
  validation,
  editorFailure,
  isAdmin,
  load,
  changePage,
  openCreate,
  openEdit,
  saveClass,
  openDetail,
  addStudent,
  removeStudent,
  archiveEditingClass,
} = useTeachingClassDirectory()
const columns: DataTableColumns<TeachingClass> = [
  {
    title: '教学班',
    key: 'name',
    minWidth: 220,
    render: (row) =>
      h('div', [
        h('strong', row.name),
        h('small', { class: 'table-subtitle' }, row.description ?? '暂无说明'),
      ]),
  },
  {
    title: '负责教师',
    key: 'teachers',
    minWidth: 170,
    render: (row) => row.teachers.map((teacher) => teacher.real_name).join('、') || '未关联',
  },
  { title: '学生人数', key: 'student_count', width: 100 },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render: (row) =>
      h(StatusBadge, {
        label: row.status === 'ACTIVE' ? '使用中' : '已归档',
        tone: row.status === 'ACTIVE' ? 'success' : 'neutral',
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 180,
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
const studentColumns: DataTableColumns<UserSummary> = [
  { title: '学号', key: 'login_name', minWidth: 130 },
  { title: '姓名', key: 'real_name', minWidth: 130 },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    render: (row) =>
      h(
        NButton,
        {
          size: 'small',
          disabled: selected.value?.status !== 'ACTIVE',
          onClick: () => removeStudent(row),
        },
        { default: () => '移出' },
      ),
  },
]
</script>

<template>
  <div class="page-stack">
    <PageHeader
      title="教学班"
      description="以成员组组织教学；多名教师可协作负责，学生可加入多个教学班。"
      ><template #actions
        ><NButton v-if="isAdmin" type="primary" @click="openCreate"
          ><template #icon><AppIcon name="plus" :size="18" /></template>新建教学班</NButton
        ></template
      ></PageHeader
    >
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重试加载</NButton></NAlert
    >
    <SurfacePanel
      title="教学班目录"
      :description="
        isAdmin ? '配置负责教师与成员；归档后保留历史关系。' : '查看并维护与你关联的教学班成员。'
      "
    >
      <div class="toolbar">
        <form class="directory-search" @submit.prevent="changePage(1)">
          <NInput
            v-model:value="query"
            :input-props="{ 'aria-label': '搜索教学班' }"
            placeholder="搜索名称或说明"
            ><template #prefix><AppIcon name="search" :size="16" /></template></NInput
          ><NButton attr-type="submit" :loading="loading">查询教学班</NButton>
        </form>
      </div>
      <div class="table-region">
        <NDataTable
          :columns="columns"
          :data="items"
          :loading="loading"
          :row-key="(row: TeachingClass) => row.id"
          :scroll-x="780"
        />
      </div>
      <ListPager
        label="教学班"
        :page="page"
        :page-size="pageSize"
        :total="total"
        :loading="loading"
        @change="changePage"
      />
    </SurfacePanel>
    <div class="section-note">
      <AppIcon name="info" :size="19" />
      <p>教学班成员变化不会联动已建立的考试名单。需要调整参考资格时，请进入相应考试处理。</p>
    </div>
    <NModal
      v-model:show="editorVisible"
      preset="card"
      :title="editingId ? '编辑教学班' : '新建教学班'"
      class="responsive-modal"
    >
      <p class="modal-intro">先定义教学班，再关联负责教师。学生成员通过“成员管理”维护。</p>
      <NAlert v-if="editorFailure" type="error" class="form-alert">{{ editorFailure }}</NAlert>
      <NForm :model="form" label-placement="top">
        <FormField v-slot="{ inputProps }" :validation="validation" field="name" label="教学班名称"
          ><NInput
            v-model:value="form.name"
            :input-props="inputProps"
            placeholder="例如：软件工程 2026"
        /></FormField>
        <NFormItem label="说明"
          ><NInput
            v-model:value="form.description"
            :input-props="{ 'aria-label': '说明' }"
            type="textarea"
            :autosize="{ minRows: 2 }"
        /></NFormItem>
        <NFormItem label="负责教师"
          ><MemberPicker
            v-if="editorVisible"
            v-model="form.teacher_ids"
            kind="teacher"
            :selected-members="selectedTeachers"
        /></NFormItem>
      </NForm>
      <template #footer
        ><div class="editor-actions editor-actions--split">
          <div>
            <NButton
              v-if="editingId && editingClass?.status === 'ACTIVE'"
              type="warning"
              @click="archiveEditingClass"
              >归档教学班</NButton
            >
          </div>
          <NSpace
            ><NButton @click="editorVisible = false">取消</NButton
            ><NButton type="primary" :loading="saving" @click="saveClass">保存</NButton></NSpace
          >
        </div></template
      >
    </NModal>
    <NModal
      v-model:show="detailVisible"
      preset="card"
      :title="selected?.name"
      class="responsive-modal--wide"
    >
      <template v-if="selected">
        <div class="class-detail-meta">
          <div>
            <p>
              负责教师：{{
                selected.teachers.map((teacher) => teacher.real_name).join('、') || '未关联'
              }}
            </p>
            <p v-if="selected.description">{{ selected.description }}</p>
          </div>
          <StatusBadge
            :label="selected.status === 'ACTIVE' ? '使用中' : '已归档'"
            :tone="selected.status === 'ACTIVE' ? 'success' : 'neutral'"
          />
        </div>
        <div v-if="selected.status === 'ACTIVE'" class="member-add">
          <MemberPicker
            v-if="detailVisible"
            :key="selected.id"
            v-model="selectedStudentIds"
            kind="student"
            :excluded-ids="selected.students?.map((student) => student.id) ?? []"
          />
          <div>
            <NButton
              type="primary"
              :disabled="!selectedStudentIds.length"
              :loading="saving"
              @click="addStudent"
              >加入学生</NButton
            >
          </div>
        </div>
        <div class="class-detail-heading">
          <h3>当前成员</h3>
          <span>{{ selected.students?.length ?? 0 }} 名学生</span>
        </div>
        <div class="table-region">
          <NDataTable :columns="studentColumns" :data="selected.students ?? []" :scroll-x="350" />
        </div>
      </template>
    </NModal>
  </div>
</template>
