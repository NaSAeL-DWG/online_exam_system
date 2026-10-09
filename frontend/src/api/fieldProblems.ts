export type ProblemFields = Record<string, string | string[]>

const labels: Record<string, string> = {
  real_name: '姓名',
  student_no: '学号',
  teacher_no: '工号',
  login_name: '登录账号',
  email: '邮箱',
  phone_number: '手机号',
  password: '密码',
  current_password: '当前密码',
  new_password: '新密码',
  temporary_password: '临时密码',
  confirmPassword: '确认密码',
  title: '名称',
  name: '名称',
  content: '题干',
  options: '选项',
  standard_answer: '参考答案',
  explanation: '解析',
  subject: '科目',
  score: '分值',
  comment: '评语',
  reason: '原因',
  description: '说明',
  start_at: '开始时间',
  end_at: '结束时间',
  duration_seconds: '作答时长',
  max_attempts: '作答次数',
  pass_percentage: '及格百分比',
  questions: '题目',
  question_id: '题目',
  grader_ids: '阅卷教师',
  version: '数据版本',
  page_size: '每页数量',
  page: '页码',
}

export function fieldLabel(path: string): string {
  const parts = path
    .replace(/^(body|query|path)\.?/, '')
    .split('.')
    .filter(Boolean)
  const field = parts.at(-1) ?? ''
  const label = labels[field] ?? '填写内容'
  const position = [...parts].reverse().find((part) => /^\d+$/.test(part))
  return position === undefined ? label : `第${Number(position) + 1}项${label}`
}

export function chineseReason(reason: unknown, fallback = '内容不符合要求，请检查后重试'): string {
  if (typeof reason !== 'string' || !/[\u3400-\u9fff]/.test(reason)) return fallback
  // 老服务或未知响应也不能把英文校验诊断直接放进用户界面。
  if (/Input should|Value error|Field required|value is not|input_value=|type=/i.test(reason))
    return fallback
  return reason
}

export function normalizeFieldErrors(fields: ProblemFields | null = {}): Record<string, string> {
  if (!fields || typeof fields !== 'object' || Array.isArray(fields)) return {}
  return Object.fromEntries(
    Object.entries(fields).map(([path, reasons]) => [
      path.replace(/^(body|query|path)\./, ''),
      [
        ...new Set(
          (Array.isArray(reasons) ? reasons : [reasons]).map((reason) => chineseReason(reason)),
        ),
      ].join('；'),
    ]),
  )
}

export function fieldErrorSummary(fields: ProblemFields = {}): string {
  return Object.entries(normalizeFieldErrors(fields))
    .map(([path, reason]) => `${fieldLabel(path)}：${reason}`)
    .join('；')
}
