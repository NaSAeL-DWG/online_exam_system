<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NAlert, NButton, NForm, NInput } from 'naive-ui'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'
import FormField from '../components/ui/FormField.vue'
import { useFormValidation } from '../composables/useFormValidation'
import { textRule, credentialRule } from '../features/identity/formRules'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
function sessionFailure(): string {
  if (route.query.reason === 'REFRESH_RESULT_UNKNOWN') return '登录状态更新未能确认，请重新登录。'
  if (route.query.reason === 'ACCOUNT_DEACTIVATED') return '账号已停用，请联系管理员。'
  return route.query.expired ? '登录状态已失效，请重新登录' : auth.restoreError
}
const failure = ref(sessionFailure())
watch(
  () => route.query,
  () => {
    failure.value = sessionFailure()
  },
)
const form = reactive({ login_name: '', password: '' })
const validation = useFormValidation(
  () => form,
  {
    login_name: textRule('登录账号'),
    password: credentialRule('密码'),
  },
  'login',
)

async function submit(): Promise<void> {
  failure.value = ''
  if (!validation.validate()) {
    failure.value = '请检查标出的填写内容'
    return
  }
  loading.value = true
  try {
    const user = await auth.login(form.login_name, form.password)
    const requested = typeof route.query.redirect === 'string' ? route.query.redirect : '/home'
    if (user.must_change_password) await router.push('/account/password')
    else if (user.user_type === 'STUDENT' && user.status === 'WAITING_ACTIVATE')
      await router.push('/student/application')
    else await router.push(requested)
  } catch (error) {
    validation.applyServerError(error)
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-form">
    <header class="auth-task-header">
      <h1>账号登录</h1>
      <p>使用学号、工号或管理员账号登录。</p>
    </header>
    <NAlert v-if="auth.notice" type="success" class="form-alert">{{ auth.notice }}</NAlert>
    <NAlert v-if="failure" type="error" class="form-alert">{{ failure }}</NAlert>
    <NForm :model="form" size="large" novalidate @submit.prevent="submit">
      <FormField
        v-slot="{ inputProps }"
        :validation="validation"
        field="login_name"
        label="登录账号"
        ><NInput
          v-model:value="form.login_name"
          :input-props="{ ...inputProps, autocomplete: 'username' }"
          placeholder="请输入登录账号"
      /></FormField>
      <FormField v-slot="{ inputProps }" :validation="validation" field="password" label="密码"
        ><NInput
          v-model:value="form.password"
          :input-props="{ ...inputProps, autocomplete: 'current-password' }"
          type="password"
          show-password-on="click"
      /></FormField>
      <NButton attr-type="submit" type="primary" block :loading="loading">登录</NButton>
    </NForm>
    <p class="auth-switch">
      <span>首次使用的学生</span><RouterLink to="/register">学生注册</RouterLink>
    </p>
  </div>
</template>
