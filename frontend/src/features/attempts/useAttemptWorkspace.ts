import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ApiError, errorMessage, isWriteResultUnknown } from '../../api/client'
import {
  studentExamsApi,
  type AnswerData,
  type AttemptDetail,
  type AttemptQuestion,
  type PagePermission,
  type StudentAnswer,
} from '../../api/studentExams'
import { createPageLease } from './pageLease'
import {
  copyAnswer,
  draftStorage,
  isUnanswered,
  normalizedAnswer,
  sameAnswer,
  type AnswerDraft,
} from './answerDrafts'

export type SaveState = 'saved' | 'unsaved' | 'saving' | 'failed' | 'conflict'
export interface AnswerRow {
  question: AttemptQuestion
  value: AnswerData
  saved: StudentAnswer
  state: SaveState
  error: string
  marked: boolean
  uncertain?: { version: number; value: AnswerData }
}
const stateMessages: Record<string, string> = {
  PAGE_TAKEN_OVER: '另一页面已接管此答卷。本页已停止保存；如需继续，请主动接管并先读取服务器答案。',
  PARTICIPANT_CANCELLED: '你的参考资格已撤销，相关作答已废弃，无法继续保存或交卷。',
  EXAM_CANCELLED: '本场考试已取消，相关作答已废弃，无法恢复。',
  ATTEMPT_EXPIRED: '作答时间已到。系统只提交截止前服务器已保存的答案，未上传的内容不计入答卷。',
  ATTEMPT_SUBMITTED: '答卷已提交，答案不能再修改。',
}
function hasConflict(row: AnswerRow): boolean {
  return row.state === 'conflict'
}

/** 工作区只编排读取、页面权限与逐题保存；计时和提交始终接受服务端状态。 */
export function useAttemptWorkspace(attemptId: string, userId: string) {
  const attempt = ref<AttemptDetail | null>(null)
  const rows = ref<AnswerRow[]>([])
  const failure = ref('')
  const notice = ref('')
  const readonlyReason = ref('')
  const loading = ref(false)
  const submitting = ref(false)
  const reloadingAnswers = ref(false)
  const permission = ref<PagePermission | null>(null)
  const remaining = ref(0)
  const missedUploads = ref(0)
  const draftUnavailable = ref(false)
  const tokenKey = `online-exam-page:${userId}:${attemptId}`
  const marksKey = `online-exam-checks:${userId}:${attemptId}`
  const canEdit = computed(
    () =>
      !!permission.value &&
      !reloadingAnswers.value &&
      !readonlyReason.value &&
      remaining.value > 0 &&
      attempt.value?.status === 'IN_PROGRESS',
  )
  const pendingCount = computed(
    () =>
      rows.value.filter((row) => row.uncertain || !sameAnswer(row.value, row.saved.answer_data))
        .length,
  )
  const emptyNumbers = computed(() =>
    rows.value.flatMap((row, index) => (isUnanswered(row.value) ? [index + 1] : [])),
  )
  const answeredCount = computed(() => rows.value.filter((row) => !isUnanswered(row.value)).length)
  const countdown = computed(() => {
    const seconds = Math.max(0, Math.ceil(remaining.value / 1000))
    return `${Math.floor(seconds / 3600)
      .toString()
      .padStart(2, '0')}:${Math.floor((seconds / 60) % 60)
      .toString()
      .padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`
  })
  let drafts: ReturnType<typeof draftStorage> | null = null
  let serverAnchor = 0
  let clockAnchor = 0
  let closed = false
  let pollBusy = false
  let activationBusy = false
  let epoch = 0
  const timers = new Map<string, ReturnType<typeof setTimeout>>()
  const writes = new Map<string, Promise<void>>()
  const lease = createPageLease(userId, attemptId, (suspended) =>
    stopWriting(
      suspended ? '页面已暂停，返回后将重新确认写权限。' : stateMessages.PAGE_TAKEN_OVER!,
    ),
  )

  function stopWriting(reason: string): void {
    epoch += 1
    readonlyReason.value = reason
    permission.value = null
    for (const timer of timers.values()) clearTimeout(timer)
    timers.clear()
  }
  function readToken(): string | undefined {
    try {
      return sessionStorage.getItem(tokenKey) || undefined
    } catch {
      return undefined
    }
  }
  function persist(): void {
    if (!drafts || !permission.value) return
    const values: Record<string, AnswerDraft> = {}
    for (const row of rows.value) {
      if (row.uncertain || !sameAnswer(row.value, row.saved.answer_data))
        values[row.saved.id] = { version: row.saved.version, value: row.value, sent: row.uncertain }
    }
    draftUnavailable.value = !drafts.write(values)
  }
  function tick(): void {
    if (!attempt.value) return
    remaining.value = Math.max(
      0,
      Date.parse(attempt.value.deadline_at) - serverAnchor - (performance.now() - clockAnchor),
    )
    if (remaining.value === 0 && attempt.value.status === 'IN_PROGRESS' && !readonlyReason.value) {
      missedUploads.value = pendingCount.value
      stopWriting(stateMessages.ATTEMPT_EXPIRED!)
      void poll()
    }
  }
  function syncClock(value: AttemptDetail): void {
    serverAnchor = Date.parse(value.server_now)
    clockAnchor = performance.now()
    remaining.value = Math.max(0, Date.parse(value.deadline_at) - serverAnchor)
  }
  function assign(value: AttemptDetail): void {
    // 换代后在途响应只能完成自己的旧请求，不能修改新行或触碰新页面草稿。
    epoch += 1
    for (const timer of timers.values()) clearTimeout(timer)
    timers.clear()
    writes.clear()
    attempt.value = value
    let marked: string[] = []
    try {
      marked = JSON.parse(sessionStorage.getItem(marksKey) || '[]') as string[]
    } catch {
      /* 标记只是检查辅助信息，不影响服务器答案。 */
    }
    rows.value = value.questions.map((question) => ({
      question,
      value: structuredClone(question.answer.answer_data),
      saved: question.answer,
      state: 'saved',
      error: '',
      marked: marked.includes(question.id),
    }))
    syncClock(value)
  }
  function restoreDraft(): void {
    const stored = drafts?.read() || {}
    let restored = 0
    let stale = 0
    for (const row of rows.value) {
      const entry = stored[row.saved.id]
      if (!entry || (!entry.sent && sameAnswer(entry.value, row.saved.answer_data))) continue
      // 版本不符的草稿仅提示，绝不把另一页面的新答案静默覆盖。
      if (
        entry.version !== row.saved.version &&
        (!entry.sent || !sameAnswer(entry.sent.value, row.saved.answer_data))
      ) {
        stale += 1
        continue
      }
      row.value = entry.value
      row.state = 'unsaved'
      if (entry.version === row.saved.version) row.uncertain = entry.sent
      restored += 1
    }
    if (restored) notice.value = `已恢复 ${restored} 题当前设备的未上传草稿，将在截止前重试保存。`
    if (stale) notice.value += ` ${stale} 题草稿版本已过时，已保留服务器答案。`
    persist()
    if (navigator.onLine) void saveAll()
  }
  async function activate(takeover: boolean): Promise<void> {
    if (!attempt.value || attempt.value.status !== 'IN_PROGRESS' || activationBusy) return
    activationBusy = true
    loading.value = true
    const originalToken = takeover ? undefined : readToken()
    // Web Lock 只约束当前浏览器；新设备看到已有代次时必须由用户明确接管。
    if (!takeover && !originalToken && attempt.value.token_generation > 0) {
      readonlyReason.value = '本答卷已在另一页面开始。本页只读；主动接管后才能保存。'
      activationBusy = false
      loading.value = false
      return
    }
    if (!(await lease.acquire(takeover))) {
      readonlyReason.value = '本答卷正在另一页面作答。本页只读；主动接管后才能保存。'
      activationBusy = false
      loading.value = false
      return
    }
    const activationEpoch = epoch
    try {
      const value = await studentExamsApi.activate(
        attemptId,
        originalToken,
        !takeover && !originalToken ? 0 : undefined,
      )
      if (closed || activationEpoch !== epoch) return
      assign(value)
      permission.value = { page_token: value.page_token, token_generation: value.token_generation }
      try {
        sessionStorage.setItem(tokenKey, value.page_token)
      } catch {
        notice.value = '浏览器未允许保存页面权限，刷新后需要重新接管。'
      }
      readonlyReason.value = ''
      failure.value = ''
      if (takeover) {
        drafts?.clear()
        notice.value = '已接管并读取服务器最新答案；旧页面未上传的草稿没有覆盖本页。'
        lease.broadcastTakeover()
      } else if (originalToken) restoreDraft()
      tick()
    } catch (error) {
      lease.release()
      handleError(error)
    } finally {
      activationBusy = false
      loading.value = false
    }
  }
  function handleError(error: unknown): void {
    const code = error instanceof ApiError ? error.problem.code : ''
    failure.value = stateMessages[code] || errorMessage(error)
    if (stateMessages[code]) {
      if (code === 'ATTEMPT_EXPIRED') missedUploads.value = pendingCount.value
      stopWriting(failure.value)
      lease.release()
      if (code === 'ATTEMPT_EXPIRED' || code === 'ATTEMPT_SUBMITTED') void poll()
    }
  }
  async function load(): Promise<void> {
    loading.value = true
    failure.value = ''
    try {
      const value = await studentExamsApi.attempt(attemptId)
      if (closed) return
      drafts = draftStorage(userId, value.exam_id, attemptId)
      assign(value)
      if (value.status === 'IN_PROGRESS') await activate(false)
      else if (value.submission_type === 'TIMEOUT') {
        const local = drafts.read()
        missedUploads.value = Object.keys(local).length
      }
    } catch (error) {
      handleError(error)
    } finally {
      loading.value = false
    }
  }
  async function poll(): Promise<void> {
    if (pollBusy || closed || !attempt.value) return
    pollBusy = true
    const pollEpoch = epoch
    try {
      const value = await studentExamsApi.attempt(attemptId)
      if (closed || pollEpoch !== epoch) return
      syncClock(value)
      if (value.status !== 'IN_PROGRESS') {
        missedUploads.value = Math.max(missedUploads.value, pendingCount.value)
        stopWriting(
          value.submission_type === 'TIMEOUT'
            ? stateMessages.ATTEMPT_EXPIRED!
            : stateMessages.ATTEMPT_SUBMITTED!,
        )
        lease.release()
        assign(value)
      } else if (permission.value && value.token_generation !== permission.value.token_generation) {
        stopWriting(stateMessages.PAGE_TAKEN_OVER!)
        lease.release()
      }
      tick()
    } catch (error) {
      if (error instanceof ApiError && stateMessages[error.problem.code]) handleError(error)
    } finally {
      pollBusy = false
    }
  }
  function change(row: AnswerRow, value: AnswerData): void {
    if (!canEdit.value || submitting.value) return
    row.value = value
    row.error = ''
    row.state = !row.uncertain && sameAnswer(value, row.saved.answer_data) ? 'saved' : 'unsaved'
    persist()
    clearTimeout(timers.get(row.saved.id))
    if (row.question.type === 'SHORT_ANSWER')
      timers.set(
        row.saved.id,
        setTimeout(() => void saveRow(row), 650),
      )
    else void saveRow(row)
  }
  function mark(row: AnswerRow): void {
    if (!canEdit.value || submitting.value) return
    row.marked = !row.marked
    try {
      sessionStorage.setItem(
        marksKey,
        JSON.stringify(rows.value.filter((item) => item.marked).map((item) => item.question.id)),
      )
    } catch {
      /* 浏览器禁用存储时仍允许当前页面检查，不阻止答题。 */
    }
  }
  async function reconcileUnknown(
    row: AnswerRow,
    sent: AnswerData,
    saveEpoch: number,
  ): Promise<boolean> {
    const current = await studentExamsApi.attempt(attemptId)
    if (saveEpoch !== epoch || closed) return false
    syncClock(current)
    if (
      current.status !== 'IN_PROGRESS' ||
      current.token_generation !== permission.value?.token_generation
    ) {
      await poll()
      return false
    }
    const answer = current.questions.find((question) => question.answer.id === row.saved.id)!.answer
    if (sameAnswer(answer.answer_data, sent)) {
      row.saved = answer
      row.uncertain = undefined
      return true
    }
    if (answer.version !== row.saved.version) {
      row.state = 'conflict'
      row.error = '服务器答案版本已改变，请重新读取服务器答案后继续。'
    } else {
      row.uncertain = undefined
    }
    return false
  }
  async function saveRow(row: AnswerRow): Promise<void> {
    clearTimeout(timers.get(row.saved.id))
    timers.delete(row.saved.id)
    const ongoing = writes.get(row.saved.id)
    const saveEpoch = epoch
    if (ongoing) {
      await ongoing
      if (saveEpoch === epoch && row.state !== 'failed' && row.state !== 'conflict')
        await saveRow(row)
      return
    }
    tick()
    if (
      !canEdit.value ||
      !permission.value ||
      (!row.uncertain && sameAnswer(row.value, row.saved.answer_data)) ||
      row.state === 'conflict'
    )
      return
    if (row.uncertain) {
      let confirmed = false
      try {
        confirmed = await reconcileUnknown(row, row.uncertain.value, saveEpoch)
      } catch {
        row.state = 'failed'
        return
      }
      if (saveEpoch !== epoch || hasConflict(row) || !canEdit.value) return
      if (confirmed && sameAnswer(row.value, row.saved.answer_data)) {
        row.state = 'saved'
        persist()
        return
      }
      // 即使用户改回已确认的旧值，也需写入最新意图，阻止尚未落库的旧请求随后改答。
    }
    const sent = copyAnswer(normalizedAnswer(row.value))
    row.uncertain = { version: row.saved.version, value: sent }
    persist()
    row.state = 'saving'
    row.error = ''
    const operation = (async () => {
      try {
        const answer = await studentExamsApi.save(
          attemptId,
          row.saved.id,
          permission.value!,
          row.saved.version,
          sent,
        )
        if (saveEpoch !== epoch || closed) return
        row.saved = answer
        row.uncertain = undefined
        row.state = sameAnswer(row.value, row.saved.answer_data) ? 'saved' : 'unsaved'
      } catch (error) {
        if (saveEpoch !== epoch || closed) return
        let confirmed = false
        if (isWriteResultUnknown(error)) {
          try {
            confirmed = await reconcileUnknown(row, sent, saveEpoch)
          } catch {
            /* 交付中断时保留本地草稿，恢复网络后先核对服务器版本。 */
          }
        }
        if (saveEpoch !== epoch || closed) return
        if (confirmed)
          row.state = sameAnswer(row.value, row.saved.answer_data) ? 'saved' : 'unsaved'
        else if (row.state !== 'conflict') {
          row.state =
            error instanceof ApiError && error.problem.code === 'VERSION_CONFLICT'
              ? 'conflict'
              : 'failed'
          row.error =
            row.state === 'conflict'
              ? '服务器答案版本已改变，请重新读取服务器答案后继续。'
              : '保存未确认，内容暂存在当前设备。请重试保存。'
          const code = error instanceof ApiError ? error.problem.code : ''
          if (stateMessages[code]) handleError(error)
        }
      } finally {
        if (saveEpoch === epoch && !closed) persist()
      }
    })()
    writes.set(row.saved.id, operation)
    await operation
    if (writes.get(row.saved.id) === operation) writes.delete(row.saved.id)
    if (saveEpoch === epoch && ['unsaved'].includes(row.state) && canEdit.value) await saveRow(row)
  }
  async function saveAll(): Promise<boolean> {
    for (const row of rows.value) await saveRow(row)
    return (
      pendingCount.value === 0 &&
      !rows.value.some((row) => row.state === 'failed' || row.state === 'conflict')
    )
  }
  async function prepareSubmission(): Promise<boolean> {
    if (!canEdit.value || submitting.value) return false
    submitting.value = true
    failure.value = ''
    try {
      const saved = await saveAll()
      if (!saved) failure.value = '仍有答案未保存成功。请先重试或处理版本冲突，再提交答卷。'
      return saved && canEdit.value
    } finally {
      submitting.value = false
    }
  }
  async function submit(): Promise<boolean> {
    if (!canEdit.value || !permission.value || submitting.value) return false
    submitting.value = true
    failure.value = ''
    const submitEpoch = epoch
    try {
      if (!(await saveAll())) {
        failure.value = '仍有答案未保存成功，答卷尚未提交。'
        return false
      }
      if (submitEpoch !== epoch || !permission.value || !canEdit.value) return false
      const value = await studentExamsApi.submit(attemptId, permission.value, true)
      if (submitEpoch !== epoch || closed) return false
      stopWriting(stateMessages.ATTEMPT_SUBMITTED!)
      lease.release()
      assign(value)
      drafts?.clear()
      return true
    } catch (error) {
      if (isWriteResultUnknown(error)) {
        await poll()
        if (attempt.value?.status === 'SUBMITTED') {
          drafts?.clear()
          return true
        }
        failure.value = '交卷结果未确认，请重新读取提交状态后再操作。'
      } else handleError(error)
      return false
    } finally {
      submitting.value = false
    }
  }
  async function reloadAnswers(): Promise<void> {
    loading.value = true
    reloadingAnswers.value = true
    for (const timer of timers.values()) clearTimeout(timer)
    timers.clear()
    const reloadEpoch = epoch
    try {
      await Promise.allSettled([...writes.values()])
      if (reloadEpoch !== epoch || closed) return
      const current = await studentExamsApi.attempt(attemptId)
      if (reloadEpoch !== epoch || closed) return
      drafts?.clear()
      assign(current)
      failure.value = ''
      notice.value = '已重新读取服务器答案，未上传的本地修改已放弃。'
      if (current.status !== 'IN_PROGRESS') stopWriting(stateMessages.ATTEMPT_SUBMITTED!)
    } catch (error) {
      handleError(error)
    } finally {
      loading.value = false
      reloadingAnswers.value = false
    }
  }
  async function networkRecovered(): Promise<void> {
    await poll()
    if (canEdit.value) await saveAll()
  }
  function visible(): void {
    if (document.visibilityState === 'visible') void poll()
  }
  function pageShown(event: PageTransitionEvent): void {
    if (event.persisted) void load()
  }
  const clockTimer = setInterval(tick, 250)
  const statusTimer = setInterval(() => void poll(), 15_000)
  window.addEventListener('online', networkRecovered)
  document.addEventListener('visibilitychange', visible)
  window.addEventListener('pageshow', pageShown)
  onMounted(load)
  onUnmounted(() => {
    closed = true
    clearInterval(clockTimer)
    clearInterval(statusTimer)
    for (const timer of timers.values()) clearTimeout(timer)
    lease.close()
    window.removeEventListener('online', networkRecovered)
    document.removeEventListener('visibilitychange', visible)
    window.removeEventListener('pageshow', pageShown)
  })
  return {
    attempt,
    rows,
    loading,
    failure,
    notice,
    readonlyReason,
    submitting,
    canEdit,
    countdown,
    remaining,
    missedUploads,
    draftUnavailable,
    pendingCount,
    emptyNumbers,
    answeredCount,
    load,
    poll,
    change,
    mark,
    saveRow,
    saveAll,
    prepareSubmission,
    submit,
    reloadAnswers,
    takeover: () => activate(true),
  }
}
