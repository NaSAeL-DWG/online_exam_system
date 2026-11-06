<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { NAlert, NButton, NModal } from 'naive-ui'
import { ApiError, errorMessage } from '../../api/client'
import { logsApi, type LogSettings } from '../../api/logs'
import LoadingSkeleton from '../../components/ui/LoadingSkeleton.vue'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{ 'update:show': [value: boolean]; 'access-denied': [] }>()
const settings = ref<LogSettings | null>(null)
const failure = ref('')
const notice = ref('')
const module = ref('')
const saving = ref(false)
const fileEnabled = ref(false)
let generation = 0
let loadingGeneration: number | null = null
let timer: ReturnType<typeof setInterval> | undefined

async function load() {
  if (saving.value || loadingGeneration !== null) return
  const current = ++generation
  loadingGeneration = current
  try {
    const result = await logsApi.settings()
    if (current === generation && props.show) {
      settings.value = result
      fileEnabled.value = result.file_enabled
      failure.value = ''
    }
  } catch (error) {
    if (current === generation && props.show) {
      if (error instanceof ApiError && [401, 403].includes(error.status)) {
        clear()
        emit('access-denied')
      }
      failure.value = errorMessage(error)
    }
  } finally {
    if (loadingGeneration === current) loadingGeneration = null
  }
}

async function save(operation: () => Promise<LogSettings>, message: string) {
  const current = ++generation
  saving.value = true
  failure.value = ''
  notice.value = ''
  try {
    const result = await operation()
    if (current !== generation || !props.show) return
    settings.value = result
    fileEnabled.value = result.file_enabled
    notice.value = message
  } catch (error) {
    if (current === generation && props.show) {
      fileEnabled.value = settings.value?.file_enabled ?? false
      if (error instanceof ApiError && [401, 403].includes(error.status)) {
        clear()
        emit('access-denied')
      }
      failure.value = errorMessage(error)
    }
  } finally {
    saving.value = false
  }
}

function setFile(event: Event) {
  const enabled = (event.target as HTMLInputElement).checked
  void save(() => logsApi.setFile(enabled), enabled ? '已开启全局文件记录' : '已关闭全局文件记录')
}

function enableDebug() {
  const name = module.value.trim()
  if (!/^[A-Za-z0-9_.-]{1,100}$/.test(name)) {
    failure.value = '模块名需为 1–100 位字母、数字、下划线、点或连字符'
    return
  }
  void save(() => logsApi.setDebug(name, true), `${name} 已开启 15 分钟详细采集`)
}

function clear() {
  generation += 1
  settings.value = null
  failure.value = ''
  notice.value = ''
  module.value = ''
  loadingGeneration = null
  clearInterval(timer)
}

watch(
  () => props.show,
  (show) => {
    clear()
    if (show) {
      void load()
      timer = setInterval(() => {
        void load()
      }, 3000)
    }
  },
  { immediate: true },
)
onBeforeUnmount(clear)
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    title="采集设置"
    class="responsive-modal"
    @update:show="emit('update:show', $event)"
  >
    <p class="modal-intro">设置对所有管理员和后台任务生效，每 3 秒同步最新状态。</p>
    <NAlert v-if="failure" type="error" class="form-alert"
      >{{ failure }} <NButton size="small" @click="load">重新读取设置</NButton></NAlert
    >
    <NAlert v-if="notice" type="success" class="form-alert">{{ notice }}</NAlert>
    <LoadingSkeleton v-if="!settings && !failure" label="正在读取采集设置" />
    <template v-if="settings">
      <div class="logs-setting-section">
        <label class="logs-file-toggle"
          ><span><strong>写入日志文件</strong><small>默认关闭 · 全局持久设置</small></span
          ><input
            v-model="fileEnabled"
            type="checkbox"
            :disabled="saving"
            aria-label="写入日志文件"
            @change="setFile"
        /></label>
        <p class="muted">
          {{
            settings.file_enabled
              ? '在线保留最近 7 天且最多 100000 条运行日志。'
              : '在线只保留最近 20000 条运行日志，不限制天数。'
          }}文件每个最大 10 MB，最多保留 5 个。关闭后已有文件保留。
        </p>
      </div>
      <div class="logs-setting-section">
        <h3>临时 DEBUG 采集</h3>
        <p class="muted">
          按模块增加详细记录，15 分钟后自动关闭。切换到 DEBUG 等级可查看已采集内容。
        </p>
        <form class="logs-debug-form" @submit.prevent="enableDebug">
          <label class="field"
            >DEBUG 模块<input
              v-model="module"
              placeholder="例如 auth、identity、worker、api"
              maxlength="100"
              pattern="[A-Za-z0-9_.-]{1,100}"
              required /></label
          ><NButton attr-type="submit" :loading="saving">开启 15 分钟</NButton>
        </form>
        <p v-if="settings.debug_modules.length === 0" class="logs-debug-empty">
          当前没有开启详细采集的模块
        </p>
        <div v-for="item in settings.debug_modules" :key="item.module" class="logs-debug-item">
          <div>
            <strong>{{ item.module }}</strong
            ><small
              >{{
                new Date(item.expires_at).toLocaleString('zh-CN', { hour12: false })
              }}
              到期自动关闭</small
            >
          </div>
          <NButton
            size="small"
            :disabled="saving"
            @click="
              save(() => logsApi.setDebug(item.module, false), `${item.module} 已关闭详细采集`)
            "
            >提前关闭</NButton
          >
        </div>
      </div>
      <p class="logs-level-note">
        操作审计独立保留。文件开关、DEBUG 调整及下载操作均会写入审计记录。
      </p>
    </template>
    <template #footer
      ><div class="editor-actions">
        <NButton @click="emit('update:show', false)">关闭采集设置</NButton>
      </div></template
    >
  </NModal>
</template>
