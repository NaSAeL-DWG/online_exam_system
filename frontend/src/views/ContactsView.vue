<script setup lang="ts">
import { reactive, ref } from 'vue'
import { NAlert, NButton, NCard, NForm, NFormItem, NInput, useMessage } from 'naive-ui'
import { errorMessage, request } from '../api/client'
import { useAuthStore } from '../stores/auth'
import type { User } from '../types'

const auth = useAuthStore()
const message = useMessage()
const form = reactive({
  email: auth.user?.email ?? '',
  phone_number: auth.user?.phone_number ?? '',
  current_password: '',
})
const failure = ref('')
const loading = ref(false)
async function submit(): Promise<void> {
  loading.value = true
  failure.value = ''
  try {
    const body = await request<{ user: User }>('/auth/contacts', {
      method: 'PUT',
      body: JSON.stringify(form),
    })
    auth.user = body.user
    form.current_password = ''
    message.success('联系方式已更新')
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
        <p class="eyebrow accent">个人资料</p>
        <h1>联系方式</h1>
        <p>更新联系方式需要验证当前密码，第一版不会标记邮箱或手机已验证。</p>
      </div>
    </header>
    <NCard
      ><NAlert v-if="failure" type="error" class="form-alert">{{ failure }}</NAlert
      ><NForm :model="form" label-placement="top" @submit.prevent="submit"
        ><NFormItem label="邮箱"
          ><NInput v-model:value="form.email" :input-props="{ 'aria-label': '邮箱' }" /></NFormItem
        ><NFormItem label="手机号"
          ><NInput
            v-model:value="form.phone_number"
            :input-props="{ 'aria-label': '手机号' }" /></NFormItem
        ><NFormItem label="当前密码"
          ><NInput
            v-model:value="form.current_password"
            :input-props="{ 'aria-label': '当前密码' }"
            type="password" /></NFormItem
        ><NButton attr-type="submit" type="primary" :loading="loading">保存联系方式</NButton></NForm
      ></NCard
    >
  </div>
</template>
