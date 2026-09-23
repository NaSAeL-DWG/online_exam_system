<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NAvatar,
  NButton,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NMenu,
  NTag,
  useMessage,
  type MenuOption,
} from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { errorMessage } from '../api/client'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const message = useMessage()
const loggingOut = ref(false)

const roleLabel = { STUDENT: '学生', TEACHER: '教师', ADMIN: '管理员' } as const
const menuOptions = computed<MenuOption[]>(() => {
  const common: MenuOption[] = [{ label: '工作台', key: '/home' }]
  if (auth.user?.user_type === 'STUDENT' && auth.user.status === 'WAITING_ACTIVATE') {
    return [
      { label: '审核状态', key: '/student/application' },
      { label: '联系方式', key: '/account/contacts' },
    ]
  }
  if (auth.user?.user_type === 'TEACHER')
    common.push({ label: '学生审核', key: '/staff/reviews' }, { label: '教学班', key: '/classes' })
  if (auth.user?.user_type === 'ADMIN')
    common.push(
      { label: '学生审核', key: '/staff/reviews' },
      { label: '账号管理', key: '/admin/accounts' },
      { label: '教学班', key: '/classes' },
    )
  common.push({ label: '账号安全', key: '/account/password' })
  return common
})

async function logout(): Promise<void> {
  if (loggingOut.value) return
  loggingOut.value = true
  try {
    await auth.logout()
    await router.push('/login')
  } catch (error) {
    message.error(errorMessage(error))
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <NLayout has-sider class="app-shell">
    <NLayoutSider bordered :width="244" class="sidebar">
      <div class="side-brand"><span>知衡</span><small>ONLINE EXAM</small></div>
      <NMenu :value="route.path" :options="menuOptions" @update:value="router.push" />
      <div class="side-help">
        <strong>需要帮助？</strong><span>请联系系统管理员处理账号问题。</span>
      </div>
    </NLayoutSider>
    <NLayout>
      <NLayoutHeader bordered class="topbar">
        <div>
          <p class="topbar-caption">在线限时考试系统</p>
          <strong>{{ auth.user?.real_name }}</strong>
        </div>
        <div class="user-actions">
          <NTag size="small" round>{{ auth.user ? roleLabel[auth.user.user_type] : '' }}</NTag>
          <NAvatar round :style="{ backgroundColor: '#356ae6' }">{{
            auth.user?.real_name.slice(0, 1)
          }}</NAvatar>
          <NButton quaternary :loading="loggingOut" @click="logout">退出登录</NButton>
        </div>
      </NLayoutHeader>
      <NLayoutContent class="workspace"><RouterView /></NLayoutContent>
    </NLayout>
  </NLayout>
</template>
