# 前端工程与开发指南 (`frontend/`)

本目录包含 **在线限时考试系统** 的 Vue 3 前端工程，基于 **Vue 3.5 + Vite 8 + TypeScript 5.9 + Naive UI + Vue Router 5 + Pinia 4 + ECharts 6 + KaTeX + Playwright** 构建，依赖版本严格锁定在 `package-lock.json` 中。

> **全局文档索引**：首次启动步骤请看 **[快速启动指南 (`../docs/quick-start.md`)](../docs/quick-start.md)**；视觉层级与配色规范请看 **[UI 视觉设计规范 (`../docs/ui-design.md`)](../docs/ui-design.md)**。

---

## 一、目录职责与代码组织

前端按 **“路由视图 (`views`) + 领域特性 (`features`) + 基础组件 (`components`) + 强类型通信 (`api`)”** 分层组织，避免把几百行表单校验、并发锁协调和网络请求全部塞进单个 `.vue` 页面文件中：

```text
frontend/src/
├── api/                  # 强类型 HTTP 客户端、CSRF 注入、跨标签页 Token 刷新协调、后端字段错误中文映射
├── components/           # 全站复用的无状态/基础 UI 组件
│   ├── ui/               # PageHeader、SurfacePanel、StatusBadge、AppSelect、LoadingSkeleton、PasswordIndicator 等
│   └── ...               # SafeMarkdown（Markdown+KaTeX 安全渲染）、ListPager、QuestionFields、MemberPicker 等
├── composables/          # 通用组合式函数（usePagedList 分页竞态管理、useFormValidation 就近校验、useUnsavedChanges 离开保护）
├── design/ & styles/     # C3 视觉系统：tokens.css 色阶变量、theme.ts Naive UI 主题映射、全局布局与基础样式
├── features/             # 按业务领域内聚的复杂状态与局部界面
│   ├── attempts/         # 学生作答工作台：Web Locks 单页面租约、BroadcastChannel 接管协调、本地草稿与单调时钟倒计时
│   ├── grading/          # 教师阅卷工作台：整卷读取、逐题打分表单、改分历史、标准答案更正、管理员任务改派
│   ├── results/          # 成绩公布、撤回及敏感结果防缓存/防迟到响应回填控制
│   ├── analytics/        # ECharts SVG 按需加载运行时、教师统计柱状图、学生趋势折线图与数据配置
│   ├── exams/            # 考试设置表单、来源试卷选择、班级名单导入、考试快照预览
│   ├── papers/           # 组卷编辑器、选题弹窗、题序调整与小数分值计算
│   ├── questions/        # 题目编辑器、四类题型动态答案表单、分类标签与校验规则
│   ├── identity/         # 账号名录、学生注册审核与密码/资料表单校验规则
│   ├── classes/          # 教学班名录与成员维护逻辑
│   ├── home/             # 角色工作台考试概览组件
│   └── logs/             # 管理员系统日志查看器、实时跟随/翻阅暂停、临时 DEBUG 与文件落盘设置
├── layouts/              # AppLayout（主工作区布局，含 204px 纯白直角侧栏）与 AuthLayout（登录/注册公共布局）
├── navigation/           # 角色导航菜单分组声明与权限过滤（与首页工作台共用入口定义）
├── stores/               # Pinia 认证状态存储（当前登录用户身份，绝不向 localStorage 写入敏感凭据）
├── views/                # 30 个路由级页面视图（串联具体用户任务）
└── router.ts             # 路由表、登录态拦截、强制改密重定向与待审核学生访问限制
```

---

## 二、核心前端机制说明

### 1. C3 视觉规范与无障碍交互约定

- **色彩与几何边界**：全局画布使用极浅冷灰 `#F6F7F9`（Neutral 50），内容卡片与侧栏/顶栏使用纯白 `#FFFFFF`，主操作按钮与焦点边框使用清亮蓝 Blue 600 `#2164CE`。左侧导航栏菜单项采用 **严格直角（`0 px` 圆角）+ `3 px` 蓝色内侧定位条**。新增样式必须引用 `src/styles/tokens.css` 中的语义变量，严禁硬编码旧版绿色或野生色值。
- **自定义下拉与骨架屏**：全站下拉框统一使用 `AppSelect.vue`（带浮层阴影、支持搜索多选与完整键盘方向键/Enter/Esc 操作）；加载状态统一使用 `LoadingSkeleton.vue`（内置 3.2 秒周期的白光横扫动画，自动遵循系统“减少动态效果”偏好）。
- **双端响应式（桌面端 + 390px 窄屏）**：每个页面保持单一明确的 `h1` 标题。宽数据表格在 390px 手机屏幕下采用 **表格容器内部局部横向滚动**，严禁设置死板的整页最小宽度导致整页出现水平滚动条。

### 2. HttpOnly Cookie 认证、CSRF 与跨标签页并发刷新

- `src/api/client.ts` 统一封装了所有 HTTP 通信：视图组件不直接调原生 `fetch`，也不触碰 Cookie 或 Token。
- 所有写请求（`POST`/`PUT`/`PATCH`/`DELETE`）自动获取并携带 `X-CSRF-Token` 请求头。
- 当 Access Token 过期需要调用 `/api/auth/refresh` 轮换单次 Refresh Token 时，客户端通过 **标签页内 Promise 合并 + 跨标签页 Web Locks** 严格串行化刷新请求，避免多个标签页同时拿同一个旧凭证去刷新而触发后端的重放吊销保护。

### 3. 学生限时作答：单页面写租约与防丢草稿 (`features/attempts/`)

- **详情不耗次数，开始才建答卷**：浏览 `StudentExamDetailView` 只读考试元信息，点击“开始考试”才消耗机会创建答卷。
- **Web Locks + BroadcastChannel 单页面写保护（`pageLease.ts`）**：
  - 每次页面加载生成独立的内存实例标识；普通刷新通过 `sessionStorage` 保留当前标签页令牌并恢复写锁。
  - 复制出来的标签页即使带了相同 `sessionStorage` 也拿不到浏览器 Web Lock，只能处于 **只读状态**。
  - 换设备或新开无令牌标签页进入已激活答卷时，默认只读并提示 **“主动接管”**；接管后递增服务端令牌代次（`token_generation`），通过 `BroadcastChannel` 通知旧页面立即释放写锁并转为只读。
- **服务端权威倒计时与防抖交卷**：倒计时基于服务端返回的 `server_now`、`deadline_at` 与浏览器单调时钟（`performance.now()`）推算，修改本地电脑系统时间无法延长作答。点击手动交卷时，先等待正在防抖或传输中的保存请求完成，再列出未作答题目供考生确认。

### 4. 阅卷工作台、成绩撤回防回填与按需图表 (`features/grading/` & `results/` & `analytics/`)

- **专注阅卷与版本冲突保护**：`StaffAttemptView` 进入隐藏全局侧栏的 `1248 px` 专注评分工作区。首次整卷完成前仅指定阅卷教师可打分（由 API `can_grade` 控制）；首阅完成后其他激活教师可填写改分原因复核改分。若遇多人并发打分触发版本冲突，页面会保留当前老师刚填的输入并提示刷新核对，防止盲目覆盖。
- **敏感成绩零缓存与防迟到响应回填**：历史成绩、答卷回看与错题绝不存入全局持久化缓存。每次重新读取或窗口切回重刷时，先清空旧数据并递增请求代次；如果老师刚刚撤回了成绩，此前在途的迟到旧响应会被直接丢弃，绝不会把已撤回的分数重新渲染回页面上。
- **ECharts SVG 按需加载**：`features/analytics/` 拆分了图表运行时与柱状图/折线图按需注册模块（采用轻量清晰的 SVG 渲染器），并提供可展开的完整数据表格与统计口径说明。

### 5. 故障反馈与未保存内容保护

- **写操作结果不确定时的安全提示**：当修改密码或联系方式的请求发出后遭遇网络中断、无法确认服务端是否已落库时，界面会明确提示用户“请先用新密码尝试登录 / 重新读取资料核对结果”，而不是盲目诱导用户重复提交。当响应头包含 `X-Session-Cleanup: pending` 时，正常提示操作已完成。
- **未保存离开拦截（`useUnsavedChanges.ts`）**：编辑题目、组卷、考试配置、打分或写错题笔记时，若有未保存修改，切换路由、关闭弹窗或刷新页面都会弹窗确认；但当登录会话失效或成绩被撤回失去查看权限时，会立即按安全规则退出或清空，不受离开弹窗阻拦。

---

## 三、本地开发、构建与端到端测试命令

所有命令在 `frontend/` 目录下运行（Node.js 24）：

```bash
# 1. 安装锁定依赖
npm ci

# 2. 启动本地开发服务器（默认监听 http://127.0.0.1:5173，并将 /api 代理到 http://127.0.0.1:18000）
npm run dev

# 3. TypeScript 类型检查与生产环境打包构建
npm run build

# 4. 代码格式检查与自动格式化（Prettier）
npm run format:check
npm run format

# 5. 运行 Playwright 真实浏览器端到端测试（需先启动后端服务并配置 ../.local/e2e.env）
set -a
source ../.local/e2e.env
set +a
npm run test:e2e -- tests/e2e/student-attempt.spec.ts --workers=1
```

> **提示**：如果需要自定义后端 API 代理地址，可复制 `.env.example` 为 `.env.local` 并修改 `VITE_API_TARGET`。浏览器访问请全程固定使用 `http://127.0.0.1:5173`，切勿与 `localhost` 混用。更多测试说明请参阅 **[测试与验证指南 (`../docs/testing.md`)](../docs/testing.md)**。
