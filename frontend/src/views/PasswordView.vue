<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NAlert, NButton, NCard, NForm, NFormItem, NInput, useMessage } from 'naive-ui'
import { errorMessage, request } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const message = useMessage()
const form = reactive({ current_password: '', new_password: '', confirmPassword: '' })
const failure = ref('')
const loading = ref(false)

async function submit(): Promise<void> {
  failure.value = ''
  if (form.new_password !== form.confirmPassword) {
    failure.value = '两次输入的新密码不一致'
    return
  }
  loading.value = true
  try {
    await request<void>('/auth/password', {
      method: 'PUT',
      body: JSON.stringify({
        current_password: form.current_password,
        new_password: form.new_password,
      }),
    })
    auth.clear()
    message.success('密码修改成功，请使用新密码重新登录')
    await router.push('/login')
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page-stack narrow-page">
    <header class="page-title">
      <div>
        <p class="eyebrow accent">账号安全</p>
        <h1>{{ auth.user?.must_change_password ? '请先修改临时密码' : '修改密码' }}</h1>
        <p>修改后旧会话会失效，请使用新密码继续。</p>
      </div>
    </header>
    <NAlert v-if="auth.user?.must_change_password" type="warning"
      >临时密码仅用于首次登录，完成修改前不能进入其他功能。</NAlert
    ><NCard
      ><NAlert v-if="failure" type="error" class="form-alert">{{ failure }}</NAlert
      ><NForm :model="form" label-placement="top" @submit.prevent="submit"
        ><NFormItem label="当前密码"
          ><NInput
            v-model:value="form.current_password"
            :input-props="{ 'aria-label': '当前密码' }"
            type="password" /></NFormItem
        ><NFormItem label="新密码"
          ><NInput
            v-model:value="form.new_password"
            :input-props="{ 'aria-label': '新密码' }"
            type="password" /></NFormItem
        ><NFormItem label="确认新密码"
          ><NInput
            v-model:value="form.confirmPassword"
            :input-props="{ 'aria-label': '确认新密码' }"
            type="password" /></NFormItem
        ><NButton attr-type="submit" type="primary" :loading="loading">保存新密码</NButton></NForm
      ></NCard
    >
  </div>
</template>
