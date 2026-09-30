<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppIcon from '../components/ui/AppIcon.vue'
import { navigationGroups, type NavigationModule } from './modules'

const props = defineProps<{ modules: NavigationModule[] }>()
defineEmits<{ navigate: [] }>()
const route = useRoute()
const groups = computed(() =>
  navigationGroups
    .map((group) => ({ ...group, items: props.modules.filter((item) => item.group === group.key) }))
    .filter((group) => group.items.length),
)
</script>

<template>
  <nav class="navigation" aria-label="主导航">
    <div v-for="group in groups" :key="group.key" class="navigation-group">
      <p class="navigation-caption">{{ group.label }}</p>
      <RouterLink
        v-for="item in group.items"
        :key="item.path"
        :to="item.path"
        class="navigation-link"
        :class="{
          'navigation-link--active':
            route.path === item.path || route.path.startsWith(`${item.path}/`),
        }"
        :aria-current="
          route.path === item.path || route.path.startsWith(`${item.path}/`) ? 'page' : undefined
        "
        @click="$emit('navigate')"
      >
        <AppIcon :name="item.icon" :size="18" /><span>{{ item.label }}</span>
      </RouterLink>
    </div>
  </nav>
</template>
