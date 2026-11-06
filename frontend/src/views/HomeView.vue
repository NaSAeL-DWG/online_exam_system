<script setup lang="ts">
import { computed } from 'vue'
import { NButton } from 'naive-ui'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import HomeExamOverview from '../features/home/HomeExamOverview.vue'
import StudentHomeView from './StudentHomeView.vue'
import { accessibleModules } from '../navigation/modules'

const auth = useAuthStore()
const router = useRouter()
const copy = computed(
  () =>
    ({
      STUDENT: { title: '学生工作台', description: '参加限时考试，维护你的个人账号资料。' },
      TEACHER: {
        title: '考试工作台',
        description: '先处理进行中的考试与待阅答卷，再准备下一场考试。',
      },
      ADMIN: {
        title: '考试工作台',
        description: '管理考试安排、参考资格与结果公布，查看阅卷整体进度。',
      },
    })[auth.user?.user_type ?? 'STUDENT'],
)
const modules = computed(() => accessibleModules(auth.user))
const support = computed(() =>
  modules.value.filter(
    (item) =>
      item.entry &&
      item.group !== 'preparation' &&
      item.group !== 'account' &&
      !['/staff/exams', '/staff/grading-tasks'].includes(item.path),
  ),
)
const preparation = computed(() =>
  modules.value.filter((item) => item.group === 'preparation' && item.entry),
)
const account = computed(() =>
  modules.value.filter((item) => item.group === 'account' && item.entry),
)
</script>

<template>
  <StudentHomeView v-if="auth.user?.user_type === 'STUDENT'" />
  <div v-else class="page-stack">
    <PageHeader
      :eyebrow="
        auth.user?.user_type === 'ADMIN' ? 'ADMIN / EXAM OPERATIONS' : 'TEACHER / WORKSPACE'
      "
      :title="copy.title"
      :description="copy.description"
    >
      <template #actions
        ><NButton type="primary" @click="router.push('/staff/exams?create=1')"
          ><template #icon><AppIcon name="plus" :size="16" /></template>创建考试</NButton
        ></template
      >
    </PageHeader>
    <HomeExamOverview>
      <template #preparation>
        <SurfacePanel title="考试准备">
          <div class="staff-preparation-list">
            <RouterLink v-for="item in preparation" :key="item.path" :to="item.path">
              <div>
                <h3>{{ item.entry!.title }}</h3>
                <p>{{ item.entry!.description }}</p>
              </div>
              <AppIcon name="arrow-right" :size="16" />
            </RouterLink>
          </div>
        </SurfacePanel>
      </template>
    </HomeExamOverview>
    <SurfacePanel
      :title="auth.user?.user_type === 'ADMIN' ? '人员与系统管理' : '教学与账号'"
      class="staff-support"
    >
      <div class="staff-support-links">
        <RouterLink
          v-for="item in [
            ...support,
            ...(auth.user?.user_type === 'ADMIN' ? preparation : []),
            ...account,
          ]"
          :key="item.path"
          :to="item.path"
          ><AppIcon :name="item.icon" :size="17" />{{ item.label
          }}<AppIcon name="arrow-right" :size="14"
        /></RouterLink>
      </div>
      <p>姓名或登录账号需要更正时，请由管理员核验后处理。</p>
    </SurfacePanel>
  </div>
</template>

<style scoped>
.staff-preparation-list {
  display: grid;
}
.staff-preparation-list > a {
  display: flex;
  align-items: center;
  gap: 16px;
  justify-content: space-between;
  padding: 18px 0;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text);
}
.staff-preparation-list > a:first-child {
  padding-top: 0;
}
.staff-preparation-list > a:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}
.staff-preparation-list h3 {
  margin: 0 0 7px;
  font-size: 14px;
  font-weight: 600;
}
.staff-preparation-list p,
.staff-support p {
  margin: 0;
  font-size: 12px;
  line-height: 1.8;
  color: var(--color-muted);
}
.staff-support-links {
  display: flex;
  flex-wrap: wrap;
  gap: 14px 28px;
  margin-bottom: 15px;
}
.staff-support-links a {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
}
</style>
