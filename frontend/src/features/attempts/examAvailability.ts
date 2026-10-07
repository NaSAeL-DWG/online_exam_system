import type { StudentExam } from '../../api/studentExams'

export const availabilityMessages: Record<string, string> = {
  PARTICIPANT_CANCELLED: '你的参考资格已撤销，相关作答已废弃。恢复资格不会恢复旧作答或已使用次数。',
  PARTICIPANT_REQUIRED: '你不在本场考试的参考名单中。',
  EXAM_CANCELLED: '本场考试已取消，相关作答已废弃，无法恢复。',
  EXAM_NOT_STARTED: '考试尚未开始，请在开放时间内参加。',
  EXAM_ENDED: '考试已结束，无法开始新的作答。',
  ATTEMPTS_EXHAUSTED: '本场考试的作答机会已用完。',
}

export function examPhase(exam: StudentExam): string {
  if (exam.status === 'CANCELLED') return '已取消'
  if (exam.participant_status === 'CANCELLED') return '资格已撤销'
  if (exam.current_attempt_status === 'IN_PROGRESS') return '作答中'
  if (!exam.start_at || !exam.end_at) return '时间未配置'
  const now = Date.parse(exam.server_now)
  if (now < Date.parse(exam.start_at)) return '未开始'
  if (now >= Date.parse(exam.end_at)) return '已结束'
  return exam.remaining_attempts > 0 ? '可参加' : '次数已用完'
}

export function examTime(value: string | null): string {
  if (!value) return '未配置'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value))
}
