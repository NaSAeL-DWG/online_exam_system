<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NAlert, NButton, NForm, NInput } from 'naive-ui'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import { errorMessage, isWriteResultUnknown } from '../api/client'
import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'
import FormField from '../components/ui/FormField.vue'
import PasswordIndicator from '../components/ui/PasswordIndicator.vue'
import { useFormValidation } from '../composables/useFormValidation'
import { credentialRule, passwordRule, confirmationRule } from '../features/identity/formRules'

const auth = useAuthStore()
const router = useRouter()
const form = reactive({ current_password: '', new_password: '', confirmPassword: '' })
const failure = ref('')
const loading = ref(false)
const uncertain = ref(false)
const validation = useFormValidation(
  () => form,
  {
    current_password: credentialRule(),
    new_password: passwordRule('新密码'),
    confirmPassword: confirmationRule('new_password', '确认新密码'),
  },
  'password',
)

async function confirmByLogin(): Promise<void> {
  auth.clear()
  await router.push('/login')
}

async function submit(): Promise<void> {
  if (loading.value || uncertain.value) return
  failure.value = ''
  if (!validation.validate()) {
    failure.value = '请检查标出的填写内容'
    return
  }
  loading.value = true
  try {
    const result = await authApi.changePassword(form.current_password, form.new_password)
    auth.clear()
    auth.notice = result.cleanupPending
      ? '密码修改成功，旧登录状态正在清理，请使用新密码重新登录'
      : '密码修改成功，请使用新密码重新登录'
    await router.push('/login')
  } catch (error) {
    validation.applyServerError(error)
    uncertain.value = isWriteResultUnknown(error)
    failure.value = uncertain.value
      ? '密码修改结果尚未确认，请使用新密码尝试登录；不要直接重复提交。'
      : errorMessage(error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page-stack narrow-page">
    <PageHeader
      :title="auth.user?.must_change_password ? '请先修改临时密码' : '修改密码'"
      description="更新登录密码，完成后使用新密码重新登录。"
    />
    <NAlert v-if="auth.user?.must_change_password" type="warning"
      >临时密码仅用于首次登录，完成修改前不能进入其他功能。</NAlert
    >
    <div class="settings-layout">
      <SurfacePanel title="设置新密码">
        <NAlert v-if="failure" :type="uncertain ? 'warning' : 'error'" class="form-alert"
          >{{ failure
          }}<NButton v-if="uncertain" @click="confirmByLogin">重新登录确认</NButton></NAlert
        >
        <NForm
          :model="form"
          class="settings-form"
          label-placement="top"
          novalidate
          @submit.prevent="submit"
        >
          <FormField
            v-slot="{ inputProps }"
            :validation="validation"
            field="current_password"
            label="当前密码"
            ><NInput
              v-model:value="form.current_password"
              :input-props="{ ...inputProps, autocomplete: 'current-password' }"
              type="password"
              show-password-on="click"
          /></FormField>
          <FormField
            v-slot="{ inputProps }"
            :validation="validation"
            field="new_password"
            label="新密码"
            ><div class="form-control-stack">
              <NInput
                v-model:value="form.new_password"
                :input-props="{ ...inputProps, autocomplete: 'new-password' }"
                type="password"
                show-password-on="click"
              /><PasswordIndicator :password="form.new_password" /></div
          ></FormField>
          <FormField
            v-slot="{ inputProps }"
            :validation="validation"
            field="confirmPassword"
            label="确认新密码"
            ><div class="form-control-stack">
              <NInput
                v-model:value="form.confirmPassword"
                :input-props="{ ...inputProps, autocomplete: 'new-password' }"
                type="password"
                show-password-on="click"
              /><PasswordIndicator
                mode="match"
                :password="form.new_password"
                :confirmation="form.confirmPassword"
              /></div
          ></FormField>
          <div class="editor-actions">
            <NButton attr-type="submit" type="primary" :loading="loading" :disabled="uncertain"
              >保存新密码</NButton
            >
          </div>
        </NForm>
      </SurfacePanel>
      <aside class="settings-aside">
        <AppIcon name="shield" :size="25" />
        <h2>密码与登录</h2>
        <p>修改成功后，旧登录会话将失效。请妥善保管新密码。</p>
        <p>如果忘记密码，请联系管理员核验身份后分配临时密码。</p>
        <p>修改结果无法确认时，页面会提供重新登录入口；请使用新密码确认。</p>
      </aside>
    </div>
  </div>
</template>
