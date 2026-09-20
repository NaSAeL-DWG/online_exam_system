<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton, NForm, NFormItem, NInput } from 'naive-ui'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const failure = ref(route.query.expired ? '登录状态已失效，请重新登录' : auth.restoreError)
const form = reactive({ login_name: '', password: '' })

async function submit(): Promise<void> {
  failure.value = ''
  loading.value = true
  try {
    const user = await auth.login(form.login_name, form.password)
    const requested = typeof route.query.redirect === 'string' ? route.query.redirect : '/home'
    if (user.must_change_password) await router.push('/account/password')
    else if (user.user_type === 'STUDENT' && user.status === 'WAITING_ACTIVATE')
      await router.push('/student/application')
    else await router.push(requested)
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-card compact-card">
    <p class="eyebrow accent">账号登录</p>
    <h2>欢迎回来</h2>
    <p class="muted">使用学号、工号或管理员账号登录。</p>
    <NAlert v-if="failure" type="error" class="form-alert">{{ failure }}</NAlert>
    <NForm :model="form" size="large" @submit.prevent="submit">
      <NFormItem label="登录账号"
        ><NInput
          v-model:value="form.login_name"
          :input-props="{ 'aria-label': '登录账号' }"
          placeholder="请输入登录账号"
      /></NFormItem>
      <NFormItem label="密码"
        ><NInput
          v-model:value="form.password"
          :input-props="{ 'aria-label': '密码' }"
          type="password"
          show-password-on="click"
      /></NFormItem>
      <NButton attr-type="submit" type="primary" block :loading="loading">登录</NButton>
    </NForm>
    <p class="auth-switch">还没有账号？<RouterLink to="/register">学生注册</RouterLink></p>
  </div>
</template>
