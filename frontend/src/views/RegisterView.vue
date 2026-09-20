<script setup lang="ts">
import { reactive, ref } from 'vue'
import { NAlert, NButton, NForm, NFormItem, NInput, NResult, useMessage } from 'naive-ui'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const message = useMessage()
const loading = ref(false)
const submitted = ref(false)
const failure = ref('')
const form = reactive({
  real_name: '',
  student_no: '',
  email: '',
  phone_number: '',
  password: '',
  confirmPassword: '',
})

async function submit(): Promise<void> {
  failure.value = ''
  if (form.password !== form.confirmPassword) {
    failure.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    await auth.register({
      real_name: form.real_name,
      student_no: form.student_no,
      email: form.email,
      phone_number: form.phone_number,
      password: form.password,
    })
    submitted.value = true
    message.success('注册申请已提交')
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-card">
    <NResult v-if="submitted" status="success" title="申请已提交" description="等待教师审核">
      <template #footer
        ><NButton type="primary" @click="$router.push('/login')"
          >登录查看审核状态</NButton
        ></template
      >
    </NResult>
    <template v-else>
      <p class="eyebrow accent">学生注册</p>
      <h2>创建你的学习账号</h2>
      <p class="muted">提交后可登录查看审核进度，审核通过即可参加考试。</p>
      <NAlert v-if="failure" type="error" class="form-alert">{{ failure }}</NAlert>
      <NForm :model="form" size="large" @submit.prevent="submit">
        <div class="form-grid two-columns">
          <NFormItem label="姓名"
            ><NInput
              v-model:value="form.real_name"
              :input-props="{ 'aria-label': '姓名' }"
              placeholder="请输入真实姓名"
          /></NFormItem>
          <NFormItem label="学号"
            ><NInput
              v-model:value="form.student_no"
              :input-props="{ 'aria-label': '学号' }"
              placeholder="请输入学号"
          /></NFormItem>
          <NFormItem label="邮箱"
            ><NInput
              v-model:value="form.email"
              :input-props="{ 'aria-label': '邮箱' }"
              placeholder="name@example.com"
          /></NFormItem>
          <NFormItem label="手机号"
            ><NInput
              v-model:value="form.phone_number"
              :input-props="{ 'aria-label': '手机号' }"
              placeholder="请输入手机号"
          /></NFormItem>
          <NFormItem label="密码"
            ><NInput
              v-model:value="form.password"
              :input-props="{ 'aria-label': '密码' }"
              type="password"
              show-password-on="click"
          /></NFormItem>
          <NFormItem label="确认密码"
            ><NInput
              v-model:value="form.confirmPassword"
              :input-props="{ 'aria-label': '确认密码' }"
              type="password"
              show-password-on="click"
          /></NFormItem>
        </div>
        <NButton attr-type="submit" type="primary" block :loading="loading">提交注册</NButton>
      </NForm>
      <p class="auth-switch">已有账号？<RouterLink to="/login">返回登录</RouterLink></p>
    </template>
  </div>
</template>
