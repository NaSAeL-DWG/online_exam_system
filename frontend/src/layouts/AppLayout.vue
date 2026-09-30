<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NDrawer, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { errorMessage } from '../api/client'
import AppIcon from '../components/ui/AppIcon.vue'
import AppNavigation from '../navigation/AppNavigation.vue'
import {
  accessibleModules,
  currentModule,
  navigationGroups,
  roleLabels,
} from '../navigation/modules'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const message = useMessage()
const loggingOut = ref(false)
const navigationOpen = ref(false)
const modules = computed(() => accessibleModules(auth.user))
const module = computed(() => currentModule(route.path, modules.value))
const section = computed(
  () => navigationGroups.find((group) => group.key === module.value?.group)?.label,
)

// 窗口切回桌面时关闭抽屉，避免与固定导航同时进入可访问树。
const mobileViewport = window.matchMedia('(max-width: 760px)')
function closeDesktopDrawer(): void {
  if (!mobileViewport.matches) navigationOpen.value = false
}
onMounted(() => mobileViewport.addEventListener('change', closeDesktopDrawer))
onUnmounted(() => mobileViewport.removeEventListener('change', closeDesktopDrawer))

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
  <div class="app-shell">
    <a class="skip-link" href="#workspace">跳至主要内容</a>
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="brand">
          <span class="brand-symbol"><AppIcon name="book" :size="21" /></span
          ><span class="brand-name">知衡</span>
        </div>
        <span class="sidebar-product">在线限时考试系统</span>
      </div>
      <AppNavigation :modules="modules" />
      <div class="sidebar-footer"><strong>账号协助</strong>身份资料或登录问题，请联系管理员。</div>
    </aside>
    <div class="app-main">
      <header class="topbar">
        <div class="topbar-location">
          <button
            class="mobile-menu-button"
            aria-label="打开导航"
            :aria-expanded="navigationOpen"
            aria-controls="mobile-navigation"
            @click="navigationOpen = true"
          >
            <AppIcon name="menu" :size="22" />
          </button>
          <span class="topbar-section">{{ section }}</span>
          <strong>{{ module?.label ?? '工作空间' }}</strong>
        </div>
        <div class="user-actions">
          <div class="user-info">
            <span class="user-avatar" aria-hidden="true">{{
              auth.user?.real_name.slice(0, 1)
            }}</span
            ><span class="user-name" :title="auth.user?.real_name">{{ auth.user?.real_name }}</span
            ><span class="user-role">{{ auth.user ? roleLabels[auth.user.user_type] : '' }}</span>
          </div>
          <NButton text :loading="loggingOut" @click="logout"
            ><template #icon><AppIcon name="logout" :size="16" /></template>退出登录</NButton
          >
        </div>
      </header>
      <main id="workspace" class="workspace" tabindex="-1"><RouterView /></main>
    </div>
    <NDrawer
      v-model:show="navigationOpen"
      placement="left"
      :width="288"
      :trap-focus="true"
      :auto-focus="true"
    >
      <div id="mobile-navigation" class="mobile-navigation">
        <div class="mobile-navigation-heading">
          <span class="brand-name">知衡</span
          ><button aria-label="关闭导航" @click="navigationOpen = false">
            <AppIcon name="close" />
          </button>
        </div>
        <AppNavigation :modules="modules" @navigate="navigationOpen = false" />
      </div>
    </NDrawer>
  </div>
</template>
