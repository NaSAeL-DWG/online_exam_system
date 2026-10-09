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
  NSelect,
  NSpace,
  NRadioButton,
  NRadioGroup,
  type DataTableColumns,
} from 'naive-ui'
import ListPager from '../components/ListPager.vue'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import FormField from '../components/ui/FormField.vue'
import PasswordIndicator from '../components/ui/PasswordIndicator.vue'
import { useAccountDirectory } from '../features/identity/useAccountDirectory'
import { roleLabels } from '../navigation/modules'
import type { User } from '../types'

const {
  users,
  loading,
  saving,
  failure,
  page,
  pageSize,
  total,
  query,
  role,
  createVisible,
  editVisible,
  resetVisible,
  selected,
  teacher,
  edit,
  temporaryPassword,
  teacherValidation,
  teacherFailure,
  editValidation,
  editFailure,
  resetValidation,
  resetFailure,
  statusOptions,
  load,
  changePage,
  search,
  changeRole,
  createTeacher,
  openEdit,
  openReset,
  resetPassword,
  confirmStatus,
} = useAccountDirectory()
const columns: DataTableColumns<User> = [
  {
    title: '姓名与账号',
    key: 'identity',
    minWidth: 210,
    render: (row) =>
      h('div', { class: 'person-cell' }, [
        h('span', { class: 'person-initial', 'aria-hidden': 'true' }, row.real_name.slice(0, 1)),
        h('div', [
          h('strong', row.real_name),
          h('small', { class: 'table-subtitle' }, row.login_name),
        ]),
      ]),
  },
  { title: '角色', key: 'user_type', width: 95, render: (row) => roleLabels[row.user_type] },
  {
    title: '状态',
    key: 'status',
    width: 120,
    render: (row) =>
      h(StatusBadge, {
        label:
          row.status === 'ACTIVATED'
            ? '已激活'
            : row.status === 'DEACTIVATED'
              ? '已停用'
              : '待审核',
        tone:
          row.status === 'ACTIVATED'
            ? 'success'
            : row.status === 'DEACTIVATED'
              ? 'danger'
              : 'warning',
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 210,
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
</script>

<template>
  <div class="page-stack">
    <PageHeader
      title="账号管理"
      description="创建教师账号，核验身份后更正资料、调整状态或人工重置密码。"
    >
      <template #actions
        ><NButton type="primary" @click="createVisible = true"
          ><template #icon><AppIcon name="plus" :size="18" /></template>新建教师</NButton
        ></template
      >
    </PageHeader>
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重试加载</NButton></NAlert
    >
    <SurfacePanel title="账号目录" description="学生注册申请由审核流程激活，资料更正不会跳过审核。">
      <div class="directory-tools">
        <NRadioGroup
          :value="role"
          name="account-role"
          aria-label="账号角色"
          @update:value="changeRole"
          ><NRadioButton value="all">全部账号</NRadioButton
          ><NRadioButton value="TEACHER">教师</NRadioButton
          ><NRadioButton value="STUDENT">学生</NRadioButton></NRadioGroup
        >
        <form class="directory-search" @submit.prevent="search">
          <NInput
            v-model:value="query"
            :input-props="{ 'aria-label': '搜索账号' }"
            placeholder="搜索账号或姓名"
            ><template #prefix><AppIcon name="search" :size="16" /></template></NInput
          ><NButton attr-type="submit" :loading="loading">查询账号</NButton>
        </form>
      </div>
      <div class="table-region">
        <NDataTable
          :columns="columns"
          :data="users"
          :loading="loading"
          :row-key="(row: User) => row.id"
          :scroll-x="640"
        />
      </div>
      <ListPager
        label="账号"
        :page="page"
        :page-size="pageSize"
        :total="total"
        :loading="loading"
        @change="changePage"
      />
    </SurfacePanel>
    <NModal
      v-model:show="createVisible"
      preset="card"
      title="新建教师账号"
      class="responsive-modal"
    >
      <p class="modal-intro">教师账号创建后直接激活，首次登录必须修改临时密码。</p>
      <NAlert v-if="teacherFailure" type="error" class="form-alert">{{ teacherFailure }}</NAlert>
      <NForm :model="teacher" label-placement="top">
        <div class="form-grid two-columns">
          <FormField
            v-slot="{ inputProps }"
            :validation="teacherValidation"
            field="teacher_no"
            label="工号"
            ><NInput
              v-model:value="teacher.teacher_no"
              :input-props="inputProps"
              placeholder="教师登录账号"
          /></FormField>
          <FormField
            v-slot="{ inputProps }"
            :validation="teacherValidation"
            field="real_name"
            label="姓名"
            ><NInput
              v-model:value="teacher.real_name"
              :input-props="inputProps"
              placeholder="真实姓名"
          /></FormField>
          <FormField
            v-slot="{ inputProps }"
            :validation="teacherValidation"
            field="email"
            label="邮箱"
            ><NInput v-model:value="teacher.email" :input-props="inputProps"
          /></FormField>
          <FormField
            v-slot="{ inputProps }"
            :validation="teacherValidation"
            field="phone_number"
            label="手机号"
            ><NInput v-model:value="teacher.phone_number" :input-props="inputProps"
          /></FormField>
        </div>
        <FormField
          v-slot="{ inputProps }"
          :validation="teacherValidation"
          field="temporary_password"
          label="临时密码"
          ><div class="form-control-stack">
            <NInput
              v-model:value="teacher.temporary_password"
              :input-props="{ ...inputProps, autocomplete: 'new-password' }"
              type="password"
              show-password-on="click"
            /><PasswordIndicator :password="teacher.temporary_password" /></div
        ></FormField>
      </NForm>
      <template #footer
        ><div class="editor-actions">
          <NButton @click="createVisible = false">取消</NButton
          ><NButton type="primary" :loading="saving" @click="createTeacher">创建教师</NButton>
        </div></template
      >
    </NModal>
    <NModal
      v-model:show="editVisible"
      preset="card"
      title="更正账号资料"
      class="responsive-modal--compact"
    >
      <p class="modal-intro">
        核验后更正 {{ selected?.real_name }} 的身份资料。停用会撤销现有登录会话。
      </p>
      <NForm :model="edit" label-placement="top">
        <NAlert v-if="editFailure" type="error" class="form-alert">{{ editFailure }}</NAlert>
        <FormField
          v-slot="{ inputProps }"
          :validation="editValidation"
          field="login_name"
          label="登录账号"
          ><NInput v-model:value="edit.login_name" :input-props="inputProps"
        /></FormField>
        <FormField
          v-slot="{ inputProps }"
          :validation="editValidation"
          field="real_name"
          label="姓名"
          ><NInput v-model:value="edit.real_name" :input-props="inputProps"
        /></FormField>
        <NFormItem label="账号状态"
          ><NSelect v-model:value="edit.status" aria-label="账号状态" :options="statusOptions"
        /></NFormItem>
      </NForm>
      <template #footer
        ><div class="editor-actions">
          <NButton @click="editVisible = false">取消</NButton
          ><NButton type="primary" :loading="saving" @click="confirmStatus">保存更正</NButton>
        </div></template
      >
    </NModal>
    <NModal
      v-model:show="resetVisible"
      preset="card"
      title="人工重置密码"
      class="responsive-modal--compact"
    >
      <div class="reset-subject">
        <AppIcon name="shield" :size="24" />
        <div>
          <strong>{{ selected?.real_name }}</strong>
          <p>{{ selected?.login_name }}</p>
        </div>
      </div>
      <NAlert type="warning">重置后旧会话立即失效，用户下次登录必须修改临时密码。</NAlert>
      <NAlert v-if="resetFailure" type="error" class="form-alert">{{ resetFailure }}</NAlert>
      <FormField
        v-slot="{ inputProps }"
        :validation="resetValidation"
        field="temporary_password"
        label="新临时密码"
        class="modal-field"
        ><div class="form-control-stack">
          <NInput
            v-model:value="temporaryPassword"
            :input-props="{ ...inputProps, autocomplete: 'new-password' }"
            type="password"
            show-password-on="click"
          /><PasswordIndicator :password="temporaryPassword" /></div
      ></FormField>
      <template #footer
        ><div class="editor-actions">
          <NButton @click="resetVisible = false">取消</NButton
          ><NButton type="warning" :loading="saving" @click="resetPassword">确认重置</NButton>
        </div></template
      >
    </NModal>
  </div>
</template>
