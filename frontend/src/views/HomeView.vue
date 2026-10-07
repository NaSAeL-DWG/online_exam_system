<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import PageHeader from '../components/ui/PageHeader.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import { accessibleModules, roleLabels } from '../navigation/modules'

const auth = useAuthStore()
const copy = computed(
  () =>
    ({
      STUDENT: { title: '学生工作台', description: '参加限时考试，维护你的个人账号资料。' },
      TEACHER: {
        title: '教师工作台',
        description: '准备题目与试卷，安排考试，处理教学与身份事务。',
      },
      ADMIN: { title: '管理工作台', description: '维护人员与教学组织，协作完成考试准备。' },
    })[auth.user?.user_type ?? 'STUDENT'],
)
const modules = computed(() => accessibleModules(auth.user))
const workspace = computed(() =>
  modules.value.filter((item) => item.group === 'workspace' && item.entry),
)
const preparation = computed(() =>
  modules.value.filter((item) => item.group === 'preparation' && item.entry),
)
const people = computed(() => modules.value.filter((item) => item.group === 'people' && item.entry))
const account = computed(() =>
  modules.value.filter((item) => item.group === 'account' && item.entry),
)
</script>

<template>
  <div class="page-stack">
    <PageHeader :title="copy.title" :description="copy.description"
      ><template #actions><StatusBadge label="账号已激活" tone="success" /></template
    ></PageHeader>
    <section v-if="workspace.length" class="home-section">
      <header class="home-section-heading">
        <h2>考试作答</h2>
        <p>查看开放时间与作答机会</p>
      </header>
      <div class="home-task-list">
        <RouterLink v-for="item in workspace" :key="item.path" :to="item.path" class="home-task">
          <AppIcon :name="item.icon" :size="21" />
          <div>
            <h3>{{ item.entry!.title }}</h3>
            <p>{{ item.entry!.description }}</p>
          </div>
          <AppIcon name="arrow-right" :size="18" />
        </RouterLink>
      </div>
    </section>
    <section v-if="preparation.length" class="home-section">
      <header class="home-section-heading">
        <h2>考试准备</h2>
        <p>题目 → 试卷 → 独立考试快照</p>
      </header>
      <div class="home-preparation">
        <RouterLink
          v-for="(item, index) in preparation"
          :key="item.path"
          :to="item.path"
          class="home-entry"
        >
          <div class="home-entry-top">
            <span class="home-entry-icon"><AppIcon :name="item.icon" :size="23" /></span
            ><span class="home-entry-step" aria-hidden="true">0{{ index + 1 }}</span>
          </div>
          <h3>{{ item.entry!.title }}</h3>
          <p>{{ item.entry!.description }}</p>
          <span class="home-entry-action"
            >{{ item.entry!.action }}<AppIcon name="arrow-right" :size="17"
          /></span>
        </RouterLink>
      </div>
    </section>
    <div class="home-secondary">
      <section v-if="people.length" class="home-section">
        <header class="home-section-heading">
          <h2>人员与教学</h2>
          <p>组织成员与账号身份</p>
        </header>
        <div class="home-task-list">
          <RouterLink v-for="item in people" :key="item.path" :to="item.path" class="home-task">
            <AppIcon :name="item.icon" :size="21" />
            <div>
              <h3>{{ item.entry!.title }}</h3>
              <p>{{ item.entry!.description }}</p>
            </div>
            <AppIcon name="arrow-right" :size="18" />
          </RouterLink>
        </div>
      </section>
      <section class="home-section">
        <header class="home-section-heading"><h2>我的账号</h2></header>
        <div class="home-account">
          <div class="home-account-identity">
            <span class="home-account-avatar" aria-hidden="true">{{
              auth.user?.real_name.slice(0, 1)
            }}</span>
            <div>
              <strong>{{ auth.user?.real_name }}</strong
              ><span
                >{{ auth.user ? roleLabels[auth.user.user_type] : '' }} ·
                {{ auth.user?.login_name }}</span
              >
            </div>
          </div>
          <div class="home-account-links">
            <RouterLink v-for="item in account" :key="item.path" :to="item.path"
              ><AppIcon :name="item.icon" :size="17" /><span>{{ item.entry!.action }}</span
              ><AppIcon name="arrow-right" :size="16"
            /></RouterLink>
          </div>
          <p v-if="auth.user?.user_type === 'STUDENT'" class="home-account-note">
            仅在点击开始作答后使用考试机会；关闭页面和断网不会暂停计时。
          </p>
          <p v-else class="home-account-note">姓名或登录账号需要更正时，请由管理员核验后处理。</p>
        </div>
      </section>
    </div>
  </div>
</template>
