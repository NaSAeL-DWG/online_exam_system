import type { User, UserRole } from '../types'

export interface NavigationModule {
  path: string
  label: string
  icon: string
  group: 'workspace' | 'preparation' | 'people' | 'account'
  roles: UserRole[]
  restricted?: 'application' | 'password' | 'contacts'
  entry?: { title: string; description: string; action: string }
}

const staff: UserRole[] = ['TEACHER', 'ADMIN']
const everyone: UserRole[] = ['STUDENT', 'TEACHER', 'ADMIN']

// 导航、工作台入口与当前模块共用一份声明，新增模块只需登记一次。
export const navigationModules: NavigationModule[] = [
  { path: '/home', label: '工作台', icon: 'home', group: 'workspace', roles: everyone },
  {
    path: '/staff/grading-tasks',
    label: '阅卷工作台',
    icon: 'check-circle',
    group: 'workspace',
    roles: staff,
    entry: {
      title: '处理人工阅卷',
      description: '完成整卷首阅，核对评分历史与后续更正。',
      action: '进入阅卷工作台',
    },
  },
  {
    path: '/student/exams',
    label: '我的考试',
    icon: 'exam',
    group: 'workspace',
    roles: ['STUDENT'],
    entry: {
      title: '参加限时考试',
      description: '阅读考试说明，开始或恢复自己的作答。',
      action: '查看我的考试',
    },
  },
  {
    path: '/student/application',
    label: '审核状态',
    icon: 'check-circle',
    group: 'workspace',
    roles: ['STUDENT'],
    restricted: 'application',
  },
  {
    path: '/staff/questions',
    label: '共享题库',
    icon: 'book',
    group: 'preparation',
    roles: staff,
    entry: {
      title: '准备共享题目',
      description: '维护四种题型，按科目、难度与知识点检索。',
      action: '进入题库',
    },
  },
  {
    path: '/staff/papers',
    label: '共享试卷',
    icon: 'paper',
    group: 'preparation',
    roles: staff,
    entry: {
      title: '组织预设试卷',
      description: '从题库选题、安排题目顺序并设置分值。',
      action: '进入试卷',
    },
  },
  {
    path: '/staff/exams',
    label: '考试管理',
    icon: 'exam',
    group: 'preparation',
    roles: staff,
    entry: {
      title: '安排与发布考试',
      description: '建立独立快照，配置考试规则和参考名单。',
      action: '进入考试',
    },
  },
  {
    path: '/staff/reviews',
    label: '学生审核',
    icon: 'check-circle',
    group: 'people',
    roles: staff,
    entry: {
      title: '审核注册申请',
      description: '核对学生身份资料，通过或说明更正原因。',
      action: '处理申请',
    },
  },
  {
    path: '/admin/accounts',
    label: '账号管理',
    icon: 'users',
    group: 'people',
    roles: ['ADMIN'],
    entry: {
      title: '维护系统账号',
      description: '创建教师账号，更正资料与处理账号恢复。',
      action: '管理账号',
    },
  },
  {
    path: '/classes',
    label: '教学班',
    icon: 'class',
    group: 'people',
    roles: staff,
    entry: {
      title: '维护教学组织',
      description: '关联负责教师，维护教学班中的学生成员。',
      action: '管理教学班',
    },
  },
  {
    path: '/account/contacts',
    label: '联系方式',
    icon: 'contact',
    group: 'account',
    roles: everyone,
    restricted: 'contacts',
    entry: {
      title: '更新联系方式',
      description: '核对邮箱与手机号，使用当前密码确认修改。',
      action: '查看联系方式',
    },
  },
  {
    path: '/account/password',
    label: '账号安全',
    icon: 'shield',
    group: 'account',
    roles: everyone,
    restricted: 'password',
    entry: {
      title: '维护账号安全',
      description: '修改登录密码；更新后使用新密码重新登录。',
      action: '修改密码',
    },
  },
]

export const navigationGroups = [
  { key: 'workspace', label: '工作空间' },
  { key: 'preparation', label: '考试准备' },
  { key: 'people', label: '人员与教学' },
  { key: 'account', label: '个人账号' },
] as const

export const roleLabels: Record<UserRole, string> = {
  STUDENT: '学生',
  TEACHER: '教师',
  ADMIN: '管理员',
}

export function accessibleModules(user: User | null): NavigationModule[] {
  if (!user) return []
  if (user.must_change_password)
    return navigationModules.filter((item) => item.restricted === 'password')
  if (user.status !== 'ACTIVATED') {
    return navigationModules.filter(
      (item) => item.restricted && item.roles.includes(user.user_type),
    )
  }
  return navigationModules.filter(
    (item) => item.roles.includes(user.user_type) && item.restricted !== 'application',
  )
}

export function currentModule(
  path: string,
  modules: NavigationModule[],
): NavigationModule | undefined {
  return modules.find((item) => path === item.path || path.startsWith(`${item.path}/`))
}
