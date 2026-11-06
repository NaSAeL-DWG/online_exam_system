<script setup lang="ts">
import { reactive, ref } from 'vue'
import { NAlert, NButton, NForm, NInput, useMessage } from 'naive-ui'
import AppIcon from '../components/ui/AppIcon.vue'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'
import FormField from '../components/ui/FormField.vue'
import PasswordIndicator from '../components/ui/PasswordIndicator.vue'
import PasswordRequirements from '../components/ui/PasswordRequirements.vue'
import { useFormValidation } from '../composables/useFormValidation'
import { profileRules, passwordRule, confirmationRule } from '../features/identity/formRules'

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
const validation = useFormValidation(
  () => form,
  {
    ...profileRules,
    password: passwordRule(),
    confirmPassword: confirmationRule('password'),
  },
  'register',
)

async function submit(): Promise<void> {
  failure.value = ''
  if (!validation.validate()) {
    failure.value = '请检查标出的填写内容'
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
    validation.applyServerError(error)
    failure.value = errorMessage(error)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-form">
    <div v-if="submitted" class="auth-success" role="status">
      <AppIcon class="auth-success-icon" name="check-circle" :size="42" />
      <h1>申请已提交</h1>
      <p>等待教师审核。你可以登录查看审核状态，资料需要更正时重新提交。</p>
      <NButton type="primary" @click="$router.push('/login')">登录查看审核状态</NButton>
    </div>
    <template v-else>
      <RouterLink class="register-back" to="/login">← 返回登录</RouterLink>
      <header class="auth-task-header">
        <div class="page-eyebrow">ACCOUNT / REGISTER</div>
        <h1>学生注册</h1>
        <p>填写真实资料，提交后登录查看身份审核进度。</p>
      </header>
      <NForm :model="form" class="register-panel" novalidate @submit.prevent="submit">
        <NAlert v-if="failure" type="error" class="form-alert">{{ failure }}</NAlert>
        <div class="form-grid two-columns">
          <FormField v-slot="{ inputProps }" :validation="validation" field="real_name" label="姓名"
            ><NInput
              v-model:value="form.real_name"
              :input-props="inputProps"
              placeholder="请输入真实姓名"
          /></FormField>
          <FormField
            v-slot="{ inputProps }"
            :validation="validation"
            field="student_no"
            label="学号"
            ><NInput
              v-model:value="form.student_no"
              :input-props="inputProps"
              placeholder="请输入学号"
          /></FormField>
          <FormField v-slot="{ inputProps }" :validation="validation" field="email" label="邮箱"
            ><NInput
              v-model:value="form.email"
              :input-props="inputProps"
              placeholder="name@example.com"
          /></FormField>
          <FormField
            v-slot="{ inputProps }"
            :validation="validation"
            field="phone_number"
            label="手机号"
            ><NInput
              v-model:value="form.phone_number"
              :input-props="inputProps"
              placeholder="请输入手机号"
          /></FormField>
          <FormField v-slot="{ inputProps }" :validation="validation" field="password" label="密码"
            ><div class="form-control-stack">
              <NInput
                v-model:value="form.password"
                :input-props="inputProps"
                type="password"
                show-password-on="click"
              /><PasswordIndicator :password="form.password" :show-requirements-hint="false" /></div
          ></FormField>
          <FormField
            v-slot="{ inputProps }"
            :validation="validation"
            field="confirmPassword"
            label="确认密码"
            ><div class="form-control-stack">
              <NInput
                v-model:value="form.confirmPassword"
                :input-props="inputProps"
                type="password"
                show-password-on="click"
              /><PasswordIndicator
                mode="match"
                :password="form.password"
                :confirmation="form.confirmPassword"
              /></div
          ></FormField>
        </div>
        <PasswordRequirements />
        <div class="editor-actions">
          <NButton attr-type="submit" type="primary" :loading="loading">提交注册</NButton>
        </div>
      </NForm>
    </template>
  </div>
</template>
