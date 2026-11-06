<script setup lang="ts">
import { h, ref } from 'vue'
import { NAlert, NButton, NDataTable, NInput, NModal, type DataTableColumns } from 'naive-ui'
import ListPager from '../components/ListPager.vue'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
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
const inspecting = ref<StudentReview | null>(null)
async function approveInspected(): Promise<void> {
  if (inspecting.value && (await decide(inspecting.value, 'APPROVED'))) inspecting.value = null
}
function rejectInspected(): void {
  if (!inspecting.value) return
  openReject(inspecting.value)
  inspecting.value = null
}
const columns: DataTableColumns<StudentReview> = [
  {
    title: '申请学生',
    key: 'identity',
    minWidth: 170,
    render: (row) => h('strong', row.submitted_profile.real_name),
  },
  {
    title: '学号',
    key: 'student_no',
    minWidth: 160,
    render: (row) => h('span', { class: 'student-number' }, row.submitted_profile.student_no),
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
      h(
        NButton,
        {
          size: 'small',
          disabled: saving.value,
          onClick: () => {
            inspecting.value = row
          },
        },
        { default: () => (row.status === 'PENDING' ? '审核资料' : '查看资料') },
      ),
  },
]
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="ADMIN / APPLICATIONS"
      title="学生审核"
      description="核对学生身份与联系方式，再决定是否激活账号。"
      ><template #actions
        ><NButton :loading="loading" @click="load">刷新</NButton></template
      ></PageHeader
    >
    <NAlert v-if="failure" type="error"
      >{{ failure }} <NButton size="small" @click="load">重试加载</NButton></NAlert
    >
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
    <SurfacePanel class="review-list-panel">
      <LoadingSkeleton v-if="loading && !items.length" variant="table" label="正在加载注册申请" />
      <div v-else class="table-region">
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
      :show="!!inspecting"
      @update:show="inspecting = null"
      preset="card"
      title="审核学生资料"
      class="responsive-modal--compact"
      :closable="!saving"
      :mask-closable="!saving"
    >
      <template v-if="inspecting">
        <dl class="review-profile">
          <dt>学号</dt>
          <dd>{{ inspecting.submitted_profile.student_no }}</dd>
          <dt>姓名</dt>
          <dd>{{ inspecting.submitted_profile.real_name }}</dd>
          <dt>邮箱</dt>
          <dd>{{ inspecting.submitted_profile.email }}</dd>
          <dt>手机号</dt>
          <dd>{{ inspecting.submitted_profile.phone_number }}</dd>
          <dt>申请时间</dt>
          <dd>{{ new Date(inspecting.submitted_at).toLocaleString('zh-CN') }}</dd>
          <template v-if="inspecting.reason"
            ><dt>拒绝原因</dt>
            <dd>{{ inspecting.reason }}</dd></template
          >
        </dl>
      </template>
      <template #footer
        ><div class="editor-actions">
          <NButton :disabled="saving" @click="inspecting = null">暂不处理</NButton
          ><template v-if="inspecting?.status === 'PENDING'"
            ><NButton :disabled="saving" @click="rejectInspected">拒绝申请</NButton
            ><NButton type="primary" :loading="saving" @click="approveInspected"
              >核验通过</NButton
            ></template
          >
        </div></template
      >
    </NModal>
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
<style scoped>
.review-list-panel :deep(.surface-panel-body) {
  padding: 0;
}
.review-list-panel :deep(.list-pager) {
  padding: 18px 22px;
}
:deep(.student-number) {
  font-family: Consolas, monospace;
}
.review-profile {
  display: grid;
  grid-template-columns: 80px minmax(0, 1fr);
  gap: 18px 20px;
  font-size: 13px;
  margin: 4px 0 16px;
}
.review-profile dt {
  color: var(--color-muted);
}
.review-profile dd {
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
