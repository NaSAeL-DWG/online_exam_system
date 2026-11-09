<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { NAlert, NButton } from 'naive-ui'
import NSelect from '../components/ui/AppSelect.vue'
import PageHeader from '../components/ui/PageHeader.vue'
import SurfacePanel from '../components/ui/SurfacePanel.vue'
import LoadingSkeleton from '../components/ui/LoadingSkeleton.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { useLogViewer } from '../features/logs/useLogViewer'
import { displayLogLine } from '../features/logs/logFormat'
import LogSettings from '../features/logs/LogSettings.vue'
import { ApiError, errorMessage } from '../api/client'
import { logsApi } from '../api/logs'
import '../features/logs/logs.css'

const {
  view,
  draft,
  entries,
  viewport,
  autoRefresh,
  autoScroll,
  following,
  loading,
  loadingHistory,
  failure,
  filterFailure,
  newCount,
  hasHistory,
  limited,
  updatedAt,
  changeView,
  applyFilters: applyViewerFilters,
  resetFilters: resetViewerFilters,
  refresh,
  loadOlder,
  onScroll,
  goLatest,
  exportQuery,
  accessDenied,
  revokeAccess,
} = useLogViewer()
const settingsVisible = ref(false)
const exporting = ref(false)
const exportFailure = ref('')
let exportGeneration = 0

function invalidateExport() {
  exportGeneration += 1
  exportFailure.value = ''
  exporting.value = false
  settingsVisible.value = false
}
function applyFilters() {
  invalidateExport()
  applyViewerFilters()
}
function resetFilters() {
  invalidateExport()
  resetViewerFilters()
}
function denySettingsAccess() {
  revokeAccess(new ApiError(403, { code: 'FORBIDDEN', message: '权限已失效' }))
}
watch(view, invalidateExport)
watch(accessDenied, (denied) => {
  if (denied) invalidateExport()
})
window.addEventListener('auth:expired', invalidateExport)
onBeforeUnmount(() => {
  invalidateExport()
  window.removeEventListener('auth:expired', invalidateExport)
})

async function download() {
  const current = ++exportGeneration
  exporting.value = true
  exportFailure.value = ''
  const selectedView = view.value
  try {
    const blob = await logsApi.download(selectedView, exportQuery())
    if (current !== exportGeneration) return
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${selectedView === 'runtime' ? '运行日志' : '操作审计'}-${new Date().toISOString().slice(0, 10)}.log`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (error) {
    if (current === exportGeneration && !revokeAccess(error))
      exportFailure.value = errorMessage(error)
  } finally {
    if (current === exportGeneration) exporting.value = false
  }
}
</script>

<template>
  <div class="page-stack logs-page">
    <PageHeader
      eyebrow="ADMIN / LOGS"
      title="系统日志"
      description="按考试与业务模块定位问题，运行日志和操作审计分别记录。"
      ><template #actions
        ><NButton :disabled="accessDenied" @click="settingsVisible = true">采集设置</NButton
        ><NButton :disabled="accessDenied" :loading="exporting" @click="download"
          >下载当前筛选</NButton
        ></template
      ></PageHeader
    >
    <NAlert v-if="exportFailure" type="error">{{ exportFailure }}</NAlert>
    <div class="logs-tabs" role="tablist" aria-label="日志视图">
      <button role="tab" :aria-selected="view === 'runtime'" @click="changeView('runtime')">
        运行日志
      </button>
      <button role="tab" :aria-selected="view === 'audit'" @click="changeView('audit')">
        操作审计
      </button>
    </div>
    <form class="logs-query" @submit.prevent="applyFilters">
      <div class="logs-searchbar">
        <label class="field logs-search"
          >关键词<input v-model="draft.q" placeholder="搜索考试编号、任务或日志内容" /></label
        ><label v-if="view === 'runtime'" class="field logs-module"
          >模块<input v-model="draft.module" placeholder="全部模块" /></label
        ><NButton attr-type="submit" :disabled="accessDenied" :loading="loading">应用筛选</NButton
        ><NButton :disabled="accessDenied" @click="resetFilters">重置筛选</NButton>
      </div>
      <details class="logs-advanced" :open="view === 'audit'">
        <summary>高级筛选</summary>
        <div class="logs-filter">
          <label class="field">开始时间<input v-model="draft.start" type="datetime-local" /></label>
          <label class="field">结束时间<input v-model="draft.end" type="datetime-local" /></label>
          <label v-if="view === 'runtime'" class="field"
            >日志等级<NSelect
              v-model:value="draft.level"
              aria-label="日志等级"
              :options="[
                { value: 'INFO', label: 'INFO · 仅信息' },
                { value: 'WARNING', label: 'WARNING · 信息和警告' },
                { value: 'ERROR', label: 'ERROR · 信息、警告和错误' },
                { value: 'DEBUG', label: 'DEBUG · 全部已采集' },
              ]"
          /></label>
          <template v-if="view === 'runtime'">
            <label class="field">任务<input v-model="draft.task" placeholder="任务名称" /></label>
            <label class="field logs-filter-wide"
              >关联 ID<input v-model="draft.correlation_id" placeholder="关联一次请求或任务"
            /></label>
          </template>
          <template v-else>
            <label class="field"
              >操作者 ID<input
                v-model="draft.actor_id"
                placeholder="操作者 UUID"
                pattern="[0-9a-fA-F-]{36}"
            /></label>
            <label class="field"
              >操作类型<input v-model="draft.action" placeholder="例如 TEACHER_CREATED"
            /></label>
            <label class="field"
              >对象类型<input v-model="draft.entity_type" placeholder="例如 user"
            /></label>
            <label class="field"
              >对象 ID<input
                v-model="draft.entity_id"
                placeholder="对象 UUID"
                pattern="[0-9a-fA-F-]{36}"
            /></label>
          </template>
        </div>
      </details>
    </form>
    <NAlert v-if="filterFailure" type="warning" class="logs-alert">{{ filterFailure }}</NAlert>
    <div class="logs-level-note" v-if="view === 'runtime'">
      等级按累计范围显示：INFO 仅信息；WARNING 包含信息；ERROR 包含信息与警告；DEBUG
      显示全部已采集记录。
    </div>
    <div v-else class="logs-level-note">审计独立保留，只显示安全操作摘要。时间按本地时区筛选。</div>
    <SurfacePanel class="logs-record-panel">
      <div class="logs-live-tools">
        <div class="logs-toggles">
          <label
            ><input v-model="autoRefresh" type="checkbox" :disabled="accessDenied" />自动刷新</label
          ><label
            ><input v-model="autoScroll" type="checkbox" :disabled="accessDenied" />自动滚动</label
          >
          <NButton size="small" :disabled="loading || accessDenied" @click="refresh"
            >立即刷新</NButton
          >
        </div>
        <span class="logs-live-status"
          ><i :class="{ active: autoRefresh }" />{{ autoRefresh ? '每 3 秒更新' : '刷新已暂停'
          }}<span v-if="updatedAt"> · {{ updatedAt }}</span></span
        >
      </div>
      <NAlert v-if="failure" type="error" class="logs-alert"
        >{{ failure }}<NButton size="small" @click="refresh">重试</NButton></NAlert
      >
      <div class="logs-history-bar">
        <NButton
          size="small"
          :disabled="!hasHistory || loading"
          :loading="loadingHistory"
          @click="loadOlder"
          >加载更早记录</NButton
        ><span>{{ entries.length }} 条已加载 · 本地时间从早到晚</span>
      </div>
      <div
        ref="viewport"
        class="logs-viewport"
        role="region"
        aria-label="日志记录"
        tabindex="0"
        :aria-busy="loading"
        @scroll="onScroll"
      >
        <div class="log-table-head" aria-hidden="true">
          <span>时间</span><span>{{ view === 'runtime' ? '级别' : '操作类型' }}</span
          ><span>{{ view === 'runtime' ? '模块' : '操作者' }}</span
          ><span>记录</span>
        </div>
        <LoadingSkeleton v-if="loading && !entries.length" :rows="5" label="正在加载日志" />
        <p v-else-if="entries.length === 0" class="logs-empty">
          {{ failure ? '日志暂未加载，请重试' : '当前筛选下暂无日志' }}
        </p>
        <details
          v-for="entry in entries"
          :key="entry.id"
          class="log-entry"
          :data-log-id="entry.id"
          :data-level="entry.level ?? 'INFO'"
        >
          <summary>
            <time :datetime="entry.timestamp" class="log-time">{{
              new Date(entry.timestamp).toLocaleTimeString('zh-CN', { hour12: false })
            }}</time>
            <StatusBadge
              v-if="view === 'runtime'"
              :label="entry.level || 'INFO'"
              :tone="
                entry.level === 'ERROR'
                  ? 'danger'
                  : entry.level === 'WARNING'
                    ? 'warning'
                    : 'neutral'
              "
            />
            <span v-else>{{ entry.action }}</span>
            <span class="log-module">{{
              view === 'runtime' ? entry.module : entry.actor_name || '系统'
            }}</span>
            <span class="log-entry-line"
              >{{ view === 'runtime' ? entry.message : entry.summary
              }}<span class="log-entry-mark" aria-hidden="true"> ›</span></span
            >
          </summary>
          <dl class="log-entry-detail">
            <dt>原始时间</dt>
            <dd>
              <time :datetime="entry.timestamp">{{ entry.timestamp }}</time>
            </dd>
            <template v-if="view === 'runtime'"
              ><dt>模块 / 任务</dt>
              <dd>{{ entry.module }} / {{ entry.task }}</dd>
              <dt>关联 ID</dt>
              <dd>{{ entry.correlation_id || '无' }}</dd>
              <dt>详细信息</dt>
              <dd>{{ entry.message }}</dd></template
            >
            <template v-else
              ><dt>操作者</dt>
              <dd>
                {{ entry.actor_name || '系统' }}<small>{{ entry.actor_id }}</small>
              </dd>
              <dt>操作 / 对象</dt>
              <dd>
                {{ entry.action }} / {{ entry.entity_type }}<small>{{ entry.entity_id }}</small>
              </dd>
              <dt>安全摘要</dt>
              <dd>{{ entry.summary }}</dd></template
            >
            <dt>记录 ID</dt>
            <dd>{{ entry.id }}</dd>
            <dt>完整记录</dt>
            <dd>{{ displayLogLine(entry) }}</dd>
          </dl>
        </details>
      </div>
      <div class="logs-follow-bar">
        <span>{{ following ? '正在跟随最新记录' : '已暂停跟随，可安心翻阅历史' }}</span
        ><NButton size="small" :type="newCount ? 'primary' : 'default'" @click="goLatest">{{
          newCount ? `${newCount} 条新日志 · 回到最新` : '回到最新'
        }}</NButton>
      </div>
      <p v-if="limited" class="logs-limit-note">
        本页最多保留 1000 条，已到显示上限。可继续加载更早记录，或回到最新重新读取。
      </p>
    </SurfacePanel>
    <p class="logs-export-note">
      下载已应用筛选范围内的完整 UTF-8 .log 文件，最多 10000 条；超过上限请缩小时间或筛选范围。
    </p>
    <LogSettings v-model:show="settingsVisible" @access-denied="denySettingsAccess" />
  </div>
</template>
