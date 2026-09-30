<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { NAlert, NButton, NForm, NFormItem, NInput, NSpin, useMessage } from 'naive-ui'
import { errorMessage } from '../api/client'
import { identityApi } from '../api/identity'
import { useAuthStore } from '../stores/auth'
import type { StudentApplication } from '../types'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import AppIcon from '../components/ui/AppIcon.vue'

const auth = useAuthStore()
const application = ref<StudentApplication | null>(null)
const loading = ref(true)
const saving = ref(false)
const failure = ref('')
const message = useMessage()
const form = reactive({ student_no: '', real_name: '', email: '', phone_number: '' })

async function load(): Promise<void> {
  loading.value = true
  failure.value = ''
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
    <PageHeader title="学生注册申请" description="查看身份审核结果，按教师说明更正申请资料。"
      ><template #actions
        ><NButton :loading="loading" @click="load">刷新审核状态</NButton></template
      ></PageHeader
    >
    <NSpin :show="loading">
      <div class="page-stack">
        <NAlert v-if="failure" type="error"
          >{{ failure }} <NButton size="small" @click="load">重试加载</NButton></NAlert
        >
        <section
          v-if="application"
          class="application-status"
          :class="{ 'application-status--rejected': application.status === 'REJECTED' }"
          aria-label="审核结果"
        >
          <AppIcon
            :name="
              application.status === 'REJECTED'
                ? 'alert'
                : application.status === 'APPROVED'
                  ? 'check-circle'
                  : 'clock'
            "
            :size="30"
          />
          <div>
            <h2>
              {{
                application.status === 'PENDING'
                  ? '申请审核中'
                  : application.status === 'APPROVED'
                    ? '身份审核已通过'
                    : '申请未通过'
              }}
            </h2>
            <p v-if="application.status === 'REJECTED'">{{ application.reason }}</p>
            <p v-else-if="application.status === 'APPROVED'">重新登录后即可进入学生工作台。</p>
            <p v-else>等待教师审核，审核期间仍可通过“联系方式”维护邮箱与手机号。</p>
            <p class="application-date">
              提交于 {{ new Date(application.submitted_at).toLocaleString('zh-CN') }}
            </p>
            <ol v-if="application.status !== 'REJECTED'" class="application-timeline">
              <li class="complete"><span>1</span>提交申请</li>
              <li :class="{ complete: application.status === 'APPROVED' }">
                <span>2</span>教师审核
              </li>
              <li :class="{ complete: application.status === 'APPROVED' }">
                <span>3</span>身份激活
              </li>
            </ol>
          </div>
        </section>
        <SurfacePanel
          v-if="application?.status === 'REJECTED'"
          title="更正后重新提交"
          description="请根据拒绝原因核对下列资料。重新提交后将再次进入审核流程。"
        >
          <NForm :model="form" label-placement="top" @submit.prevent="resubmit">
            <div class="form-grid two-columns">
              <NFormItem label="姓名"
                ><NInput v-model:value="form.real_name" :input-props="{ 'aria-label': '姓名' }"
              /></NFormItem>
              <NFormItem label="学号"
                ><NInput v-model:value="form.student_no" :input-props="{ 'aria-label': '学号' }"
              /></NFormItem>
              <NFormItem label="邮箱"
                ><NInput v-model:value="form.email" :input-props="{ 'aria-label': '邮箱' }"
              /></NFormItem>
              <NFormItem label="手机号"
                ><NInput
                  v-model:value="form.phone_number"
                  :input-props="{ 'aria-label': '手机号' }"
              /></NFormItem>
            </div>
            <div class="editor-actions">
              <NButton attr-type="submit" type="primary" :loading="saving">重新提交审核</NButton>
            </div>
          </NForm>
        </SurfacePanel>
        <SurfacePanel v-if="application" title="提交资料"
          ><dl class="profile-grid">
            <div>
              <dt>姓名</dt>
              <dd>{{ application.submitted_profile.real_name }}</dd>
            </div>
            <div>
              <dt>学号</dt>
              <dd>{{ application.submitted_profile.student_no }}</dd>
            </div>
            <div>
              <dt>邮箱</dt>
              <dd>{{ application.submitted_profile.email }}</dd>
            </div>
            <div>
              <dt>手机号</dt>
              <dd>{{ application.submitted_profile.phone_number }}</dd>
            </div>
          </dl></SurfacePanel
        >
      </div>
    </NSpin>
  </div>
</template>
