<script setup lang="ts">
import { reactive, ref } from 'vue'
import { NAlert, NButton, NForm, NFormItem, NInput, useMessage } from 'naive-ui'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import AppIcon from '../components/ui/AppIcon.vue'
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
    <PageHeader title="联系方式" description="维护邮箱和手机号，使用当前密码确认本次修改。" />
    <div class="settings-layout">
      <SurfacePanel title="更新联系资料">
        <NAlert v-if="failure" :type="uncertain ? 'warning' : 'error'" class="form-alert"
          >{{ failure
          }}<NButton v-if="uncertain" :loading="loading" @click="reloadContacts"
            >重新读取资料</NButton
          ></NAlert
        >
        <NForm :model="form" class="settings-form" label-placement="top" @submit.prevent="submit">
          <NFormItem label="邮箱"
            ><NInput
              v-model:value="form.email"
              :input-props="{ 'aria-label': '邮箱', autocomplete: 'email' }"
              placeholder="name@example.com"
          /></NFormItem>
          <NFormItem label="手机号"
            ><NInput
              v-model:value="form.phone_number"
              :input-props="{ 'aria-label': '手机号', autocomplete: 'tel' }"
          /></NFormItem>
          <NFormItem label="当前密码"
            ><NInput
              v-model:value="form.current_password"
              :input-props="{ 'aria-label': '当前密码', autocomplete: 'current-password' }"
              type="password"
              show-password-on="click"
          /></NFormItem>
          <div class="editor-actions">
            <NButton attr-type="submit" type="primary" :loading="loading" :disabled="uncertain"
              >保存联系方式</NButton
            >
          </div>
        </NForm>
      </SurfacePanel>
      <aside class="settings-aside">
        <AppIcon name="contact" :size="25" />
        <h2>资料核验</h2>
        <p>联系方式修改需要验证当前密码。</p>
        <p>邮箱与手机验证功能尚未启用，填写或修改资料不会将它们标记为已验证。</p>
        <p>姓名、学号或工号需要更正时，请联系管理员。</p>
      </aside>
    </div>
  </div>
</template>
