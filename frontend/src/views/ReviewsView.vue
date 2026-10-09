<script setup lang="ts">
import { h } from 'vue'
import {
  NAlert,
  NButton,
  NDataTable,
  NInput,
  NModal,
  NSpace,
  type DataTableColumns,
} from 'naive-ui'
import ListPager from '../components/ListPager.vue'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import FormField from '../components/ui/FormField.vue'
import { useRegistrationReviews } from '../features/identity/useRegistrationReviews'
import type { StudentReview } from '../types'

const {
  items,
  loading,
  saving,
  failure,
  page,
  pageSize,
  total,
  query,
  selected,
  rejectVisible,
  reason,
  rejectValidation,
  rejectFailure,
  load,
  changePage,
  decide,
  openReject,
} = useRegistrationReviews()
const columns: DataTableColumns<StudentReview> = [
  {
    title: '申请学生',
    key: 'identity',
    minWidth: 170,
    render: (row) =>
      h('div', [
        h('strong', row.submitted_profile.real_name),
        h('small', { class: 'table-subtitle' }, row.submitted_profile.student_no),
      ]),
  },
  {
    title: '联系方式',
    key: 'contact',
    minWidth: 200,
    render: (row) =>
      h('div', [
        h('div', row.submitted_profile.email),
        h('small', { class: 'table-subtitle' }, row.submitted_profile.phone_number),
      ]),
  },
  {
    title: '提交时间',
    key: 'submitted_at',
    minWidth: 160,
    render: (row) => new Date(row.submitted_at).toLocaleString('zh-CN'),
  },
  {
    title: '审核结果',
    key: 'status',
    width: 120,
    render: (row) =>
      h(StatusBadge, {
        label:
          row.status === 'PENDING' ? '待审核' : row.status === 'APPROVED' ? '已通过' : '已拒绝',
        tone:
          row.status === 'PENDING' ? 'warning' : row.status === 'APPROVED' ? 'success' : 'danger',
      }),
  },
  {
    title: '操作',
    key: 'actions',
    width: 160,
    render: (row) =>
      row.status === 'PENDING'
        ? h(
            NSpace,
            {},
            {
              default: () => [
                h(
                  NButton,
                  {
                    size: 'small',
                    type: 'primary',
                    disabled: saving.value,
                    onClick: () => decide(row, 'APPROVED'),
                  },
                  { default: () => '通过' },
                ),
                h(
                  NButton,
                  { size: 'small', disabled: saving.value, onClick: () => openReject(row) },
                  { default: () => '拒绝' },
                ),
              ],
            },
          )
        : h('span', { class: 'muted' }, '已处理'),
  },
]
</script>

<template>
  <div class="page-stack">
    <PageHeader
      title="学生注册审核"
      description="核对申请学生的真实身份；拒绝时说明需要更正的内容。"
      ><template #actions
        ><NButton :loading="loading" @click="load">刷新</NButton></template
      ></PageHeader
    >
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重试加载</NButton></NAlert
    >
    <SurfacePanel title="注册申请" description="通过后开放学生账号权限，已处理申请保留审核记录。">
      <div class="toolbar">
        <form class="directory-search" @submit.prevent="changePage(1)">
          <NInput
            v-model:value="query"
            :input-props="{ 'aria-label': '搜索申请' }"
            placeholder="搜索姓名或学号"
            ><template #prefix><AppIcon name="search" :size="16" /></template></NInput
          ><NButton attr-type="submit" :loading="loading">查询申请</NButton>
        </form>
      </div>
      <div class="table-region">
        <NDataTable
          :columns="columns"
          :data="items"
          :loading="loading"
          :row-key="(row: StudentReview) => row.id"
          :scroll-x="810"
        />
      </div>
      <ListPager
        label="审核"
        :page="page"
        :page-size="pageSize"
        :total="total"
        :loading="loading"
        @change="changePage"
      />
    </SurfacePanel>
    <NModal
      v-model:show="rejectVisible"
      preset="card"
      title="拒绝学生申请"
      class="responsive-modal--compact"
    >
      <div class="reset-subject">
        <AppIcon name="user" :size="24" />
        <div>
          <strong>{{ selected?.submitted_profile.real_name }}</strong>
          <p>{{ selected?.submitted_profile.student_no }}</p>
        </div>
      </div>
      <NAlert v-if="rejectFailure" type="error" class="form-alert">{{ rejectFailure }}</NAlert>
      <FormField
        v-slot="{ inputProps }"
        :validation="rejectValidation"
        field="reason"
        label="拒绝原因"
        ><NInput
          v-model:value="reason"
          type="textarea"
          :input-props="inputProps"
          placeholder="说明资料中需要更正的内容"
          :autosize="{ minRows: 4 }"
      /></FormField>
      <p class="muted">学生将看到此说明，并可更正资料后重新提交。</p>
      <template #footer
        ><div class="editor-actions">
          <NButton @click="rejectVisible = false">取消</NButton
          ><NButton type="error" :loading="saving" @click="selected && decide(selected, 'REJECTED')"
            >确认拒绝</NButton
          >
        </div></template
      >
    </NModal>
  </div>
</template>
