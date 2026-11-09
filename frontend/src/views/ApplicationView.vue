<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { NAlert, NButton, NForm, NInput, useMessage } from 'naive-ui'
import { errorMessage } from '../api/client'
import { identityApi } from '../api/identity'
import { useAuthStore } from '../stores/auth'
import type { StudentApplication } from '../types'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import FormField from '../components/ui/FormField.vue'
import { useFormValidation } from '../composables/useFormValidation'
import { profileRules } from '../features/identity/formRules'

const auth = useAuthStore()
const application = ref<StudentApplication | null>(null)
const loading = ref(true)
const saving = ref(false)
const failure = ref('')
const message = useMessage()
const form = reactive({ student_no: '', real_name: '', email: '', phone_number: '' })
const validation = useFormValidation(() => form, profileRules, 'application')

async function load(): Promise<void> {
  loading.value = true
  failure.value = ''
  try {
    application.value = (await identityApi.application()).application
    Object.assign(form, application.value.submitted_profile)
    validation.clear()
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}
async function resubmit(): Promise<void> {
  if (saving.value) return
  failure.value = ''
  if (!validation.validate()) {
    failure.value = '请检查标出的填写内容'
    return
  }
  saving.value = true
  try {
    application.value = (await identityApi.resubmitApplication(form)).application
    await auth.restore()
    message.success('申请已重新提交')
  } catch (error) {
    validation.applyServerError(error)
    failure.value = errorMessage(error)
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>

<template>
  <div class="page-stack application-page">
    <PageHeader
      eyebrow="ACCOUNT / APPLICATION"
      title="学生注册申请"
      description="账号激活后，即可查看考试安排并参加考试。"
      ><template #actions
        ><NButton :loading="loading" @click="load">刷新审核状态</NButton></template
      ></PageHeader
    >
    <LoadingSkeleton v-if="loading && !application" variant="detail" label="正在读取审核状态" />
    <div v-else class="page-stack" :aria-busy="loading">
      <NAlert v-if="failure" type="error"
        >{{ failure }}
        <NButton v-if="!application" size="small" @click="load">重试加载</NButton></NAlert
      >
      <SurfacePanel v-if="application" aria-label="审核结果">
        <div class="application-summary-heading">
          <h2>
            {{
              application.status === 'PENDING'
                ? '申请审核中'
                : application.status === 'APPROVED'
                  ? '身份审核已通过'
                  : '申请未通过'
            }}
          </h2>
          <StatusBadge
            :label="
              application.status === 'REJECTED'
                ? '待更正'
                : application.status === 'APPROVED'
                  ? '已通过'
                  : '待审核'
            "
            :tone="
              application.status === 'REJECTED'
                ? 'danger'
                : application.status === 'APPROVED'
                  ? 'success'
                  : 'neutral'
            "
          />
        </div>
        <NAlert
          :type="
            application.status === 'REJECTED'
              ? 'error'
              : application.status === 'APPROVED'
                ? 'success'
                : 'info'
          "
          :show-icon="false"
        >
          <strong>{{
            application.status === 'REJECTED'
              ? '请按审核意见更正资料'
              : application.status === 'APPROVED'
                ? '资料核验完成'
                : '资料已收到'
          }}</strong>
          <p v-if="application.status === 'REJECTED'">{{ application.reason }}</p>
          <p v-else-if="application.status === 'APPROVED'">重新登录后即可进入学生工作台。</p>
          <p v-else>请耐心等待教师核验。审核期间仍可维护联系方式。</p>
          <p>提交于 {{ new Date(application.submitted_at).toLocaleString('zh-CN') }}</p>
        </NAlert>
        <dl class="application-profile">
          <dt>姓名</dt>
          <dd>{{ application.submitted_profile.real_name }}</dd>
          <dt>学号</dt>
          <dd>{{ application.submitted_profile.student_no }}</dd>
          <dt>邮箱</dt>
          <dd>{{ application.submitted_profile.email }}</dd>
          <dt>手机号</dt>
          <dd>{{ application.submitted_profile.phone_number }}</dd>
        </dl>
        <ol v-if="application.status !== 'REJECTED'" class="application-timeline">
          <li class="complete"><span>1</span>提交申请</li>
          <li :class="{ complete: application.status === 'APPROVED' }"><span>2</span>教师审核</li>
          <li :class="{ complete: application.status === 'APPROVED' }"><span>3</span>身份激活</li>
        </ol>
        <RouterLink
          v-if="application.status !== 'REJECTED'"
          to="/account/contacts"
          class="application-contact"
          >维护联系方式 →</RouterLink
        >
      </SurfacePanel>
      <SurfacePanel
        v-if="application?.status === 'REJECTED'"
        title="更正后重新提交"
        description="请根据拒绝原因核对下列资料。重新提交后将再次进入审核流程。"
      >
        <NForm :model="form" label-placement="top" novalidate @submit.prevent="resubmit">
          <div class="form-grid two-columns">
            <FormField
              v-slot="{ inputProps }"
              :validation="validation"
              field="real_name"
              label="姓名"
              ><NInput v-model:value="form.real_name" :input-props="inputProps"
            /></FormField>
            <FormField
              v-slot="{ inputProps }"
              :validation="validation"
              field="student_no"
              label="学号"
              ><NInput v-model:value="form.student_no" :input-props="inputProps"
            /></FormField>
            <FormField v-slot="{ inputProps }" :validation="validation" field="email" label="邮箱"
              ><NInput v-model:value="form.email" :input-props="inputProps"
            /></FormField>
            <FormField
              v-slot="{ inputProps }"
              :validation="validation"
              field="phone_number"
              label="手机号"
              ><NInput v-model:value="form.phone_number" :input-props="inputProps"
            /></FormField>
          </div>
          <div class="editor-actions">
            <NButton attr-type="submit" type="primary" :loading="saving">重新提交审核</NButton>
          </div>
        </NForm>
      </SurfacePanel>
    </div>
  </div>
</template>

<style scoped>
.application-page {
  max-width: 760px;
  margin-left: 0;
}
.application-summary-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}
.application-summary-heading h2 {
  font-size: 17px;
  margin: 0;
}
.application-profile {
  display: grid;
  grid-template-columns: 108px minmax(0, 1fr);
  gap: 14px 20px;
  margin: 24px 0;
  font-size: 13px;
}
.application-profile dt {
  color: var(--color-muted);
}
.application-profile dd {
  margin: 0;
  overflow-wrap: anywhere;
}
.application-contact {
  display: inline-block;
  margin-top: 24px;
  font-size: 13px;
}
.n-alert p {
  margin: 6px 0 0;
}
@media (max-width: 600px) {
  .application-summary-heading {
    align-items: flex-start;
  }
  .application-profile {
    grid-template-columns: 64px minmax(0, 1fr);
  }
}
</style>
