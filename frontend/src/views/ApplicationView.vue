<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDescriptions,
  NDescriptionsItem,
  NForm,
  NFormItem,
  NInput,
  NResult,
  NSpin,
  useMessage,
} from 'naive-ui'
import { errorMessage } from '../api/client'
import { identityApi } from '../api/identity'
import { useAuthStore } from '../stores/auth'
import type { StudentApplication } from '../types'

const auth = useAuthStore()
const application = ref<StudentApplication | null>(null)
const loading = ref(true)
const saving = ref(false)
const failure = ref('')
const message = useMessage()
const form = reactive({ student_no: '', real_name: '', email: '', phone_number: '' })

async function load(): Promise<void> {
  loading.value = true
  try {
    application.value = (await identityApi.application()).application
    Object.assign(form, application.value.submitted_profile)
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}
async function resubmit(): Promise<void> {
  saving.value = true
  failure.value = ''
  try {
    application.value = (await identityApi.resubmitApplication(form)).application
    await auth.restore()
    message.success('申请已重新提交')
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>

<template>
  <div class="page-stack narrow-page">
    <header class="page-title">
      <div>
        <p class="eyebrow accent">身份审核</p>
        <h1>学生注册申请</h1>
        <p>你可以在这里查看教师审核结果。</p>
      </div>
    </header>
    <NSpin :show="loading"
      ><NAlert v-if="failure" type="error" class="form-alert">{{ failure }}</NAlert
      ><NResult
        v-if="application?.status === 'PENDING'"
        status="info"
        title="申请审核中"
        description="等待教师审核，审核期间仍可修改联系方式。"
      /><NResult
        v-else-if="application?.status === 'APPROVED'"
        status="success"
        title="身份审核已通过"
        description="重新登录后即可进入学生工作台。"
      /><template v-else-if="application?.status === 'REJECTED'"
        ><NAlert type="error" title="申请未通过">{{ application.reason }}</NAlert
        ><NCard title="更正后重新提交"
          ><NForm :model="form" label-placement="top" @submit.prevent="resubmit"
            ><div class="form-grid two-columns">
              <NFormItem label="姓名"
                ><NInput
                  v-model:value="form.real_name"
                  :input-props="{ 'aria-label': '姓名' }" /></NFormItem
              ><NFormItem label="学号"
                ><NInput
                  v-model:value="form.student_no"
                  :input-props="{ 'aria-label': '学号' }" /></NFormItem
              ><NFormItem label="邮箱"
                ><NInput
                  v-model:value="form.email"
                  :input-props="{ 'aria-label': '邮箱' }" /></NFormItem
              ><NFormItem label="手机号"
                ><NInput
                  v-model:value="form.phone_number"
                  :input-props="{ 'aria-label': '手机号' }"
              /></NFormItem>
            </div>
            <NButton attr-type="submit" type="primary" :loading="saving"
              >重新提交审核</NButton
            ></NForm
          ></NCard
        ></template
      ><NCard v-if="application" title="提交资料"
        ><NDescriptions :column="2" label-placement="left"
          ><NDescriptionsItem label="姓名">{{
            application.submitted_profile.real_name
          }}</NDescriptionsItem
          ><NDescriptionsItem label="学号">{{
            application.submitted_profile.student_no
          }}</NDescriptionsItem
          ><NDescriptionsItem label="邮箱">{{
            application.submitted_profile.email
          }}</NDescriptionsItem
          ><NDescriptionsItem label="手机号">{{
            application.submitted_profile.phone_number
          }}</NDescriptionsItem></NDescriptions
        ></NCard
      ></NSpin
    >
  </div>
</template>
