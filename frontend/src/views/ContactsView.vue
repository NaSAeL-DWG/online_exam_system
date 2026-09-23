<script setup lang="ts">
import { reactive, ref } from 'vue'
import { NAlert, NButton, NCard, NForm, NFormItem, NInput, useMessage } from 'naive-ui'
import { errorMessage, isWriteResultUnknown } from '../api/client'
import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const message = useMessage()
const form = reactive({
  email: auth.user?.email ?? '',
  phone_number: auth.user?.phone_number ?? '',
  current_password: '',
})
const failure = ref('')
const loading = ref(false)
const uncertain = ref(false)

async function reloadContacts(): Promise<void> {
  loading.value = true
  try {
    const result = await authApi.me()
    auth.user = result.user
    form.email = result.user.email
    form.phone_number = result.user.phone_number
    form.current_password = ''
    uncertain.value = false
    failure.value = ''
    message.success('已读取最新联系方式，请核对保存结果')
  } catch (error) {
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}
async function submit(): Promise<void> {
  if (loading.value || uncertain.value) return
  loading.value = true
  failure.value = ''
  try {
    const result = await authApi.changeContacts(form)
    auth.user = result.data.user
    form.current_password = ''
    message.success(
      result.cleanupPending ? '联系方式已更新，安全校验记录正在清理' : '联系方式已更新',
    )
  } catch (error) {
    uncertain.value = isWriteResultUnknown(error)
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
      ><NAlert v-if="failure" :type="uncertain ? 'warning' : 'error'" class="form-alert"
        >{{ failure
        }}<NButton v-if="uncertain" :loading="loading" @click="reloadContacts"
          >重新读取资料</NButton
        ></NAlert
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
        ><NButton attr-type="submit" type="primary" :loading="loading" :disabled="uncertain"
          >保存联系方式</NButton
        ></NForm
      ></NCard
    >
  </div>
</template>
