# 前端开发说明

前端使用 Vue 3、Vite、TypeScript、Naive UI、Vue Router、Pinia、ECharts 和 Playwright。依赖版本已锁定在 `package-lock.json`。

## 页面结构与扩展

本轮整体重构的范围、设计要求和验证证据见[前端重构迭代](../docs/前端重构迭代.md)。前端按以下职责组织：

- `src/design/theme.ts` 与 `src/styles/`：Naive UI 主题、设计 token、共用基础样式和应用布局。页面内使用语义 token，新增样式优先放所属组件的 scoped 区域。
- `src/components/ui/`：统一页面标题、内容面板、状态徽标和 SVG 图标；不在这些基础组件中加入业务请求。
- `src/navigation/`：角色可见性、业务分组、当前模块和工作台入口。导航与首页共用模块声明，权限受限账号只显示其可用入口。
- `src/views/`：页面组合及路由入口；`src/features/`：题目编辑、试卷编排等业务状态与局部界面。复杂编辑流程按职责组合，避免将所有表单和状态塞入一个页面。
- `src/composables/usePagedList.ts`：列表页的分页、加载、失败及请求竞争处理；筛选条件和 API 调用仍由所属业务提供。
- `src/api/` 与 `src/stores/`：公开通信契约和身份状态，视觉组件不直接处理 Cookie、刷新凭据或原始 fetch。

新增后续业务时，先实现对应 API 与业务模块，在 `router.ts` 声明路由及访问条件，再在 `navigation/modules.ts` 登记实际可用的入口。导航隐藏不能替代路由和后端权限检查。迭代 5 已实现公布、历史、回看、错题与教师统计页面；学生分析页面仍待完成，不显示可点击空入口。

页面采用一个明确的 `h1`；详情页优先突出当前对象名称，状态用徽标表达。主操作放在标题区，筛选和辅助操作使用次级强调。编辑表单保留可访问标签和失败反馈，长表格局部滚动，小屏不能通过固定页面最小宽度处理。

## 本地启动

后端默认监听 `http://127.0.0.1:18000`，前端开发服务器会把 `/api` 代理到该地址。

```bash
npm ci
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`。如需修改后端地址，复制 `.env.example` 为 `.env.local` 并更改 `VITE_API_TARGET`。

## 检查与流程测试

```bash
npm run build
npm run format:check
set -a
source ../.local/e2e.env
set +a
npm run test:e2e
```

浏览器流程连接真实 API、PostgreSQL 和 Redis。管理员凭据通过 `E2E_ADMIN_LOGIN`、`E2E_ADMIN_PASSWORD` 注入，不能写入仓库。`E2E_BASE_URL` 可覆盖前端地址，未提供时 Playwright 会自行启动 5173 端口的开发服务器。

## API 与列表约定

`src/api/auth.ts`、`identity.ts`、`teachingClasses.ts` 提供带输入和输出类型的业务操作。视图不自行拼接请求、处理 Cookie 或轮换凭据。`client.ts` 统一处理 CSRF、HttpOnly Cookie 请求、标签页内刷新合并和 Web Locks 跨标签页协调；不向 localStorage 写入认证凭据。

账号、审核、教学班和教师／学生候选统一发送 `page`、`page_size`、可选 `q`，读取 `{ items, total, page, page_size }`。账号角色筛选由服务端完成；候选接口显式筛选已激活账号。列表与候选每页 20 条，通过搜索或翻页访问后续结果，不循环拉取全量数据。已选教师独立于候选页保留，编辑时从班级详情恢复姓名和 ID。班级详情的现有成员仍按需一次读取，与列表只返回人数的契约保持一致。

## 故障与成功反馈

- 写入成功且 `X-Session-Cleanup: pending` 时，展示“已完成，旧登录状态正在清理”等成功反馈，不重新发送业务操作。
- 写请求已发出后连接中断，或成功响应的 JSON 无法读取时，结果可能已经保存。界面提示先核对结果；改密通过新密码重新登录确认，联系方式通过重新读取资料确认。
- 刷新前的 503 保留当前页面并允许手动重试。刷新请求的交付中断提示重新登录，避免自动重放单次凭据。停用和失效会话清除本地身份并回到登录页；匿名访问注册页不被误跳转。

## 验证范围

原有 4 条注册、拒绝重申、教师首次改密、教学班维护流程继续使用真实服务。`server-pagination.spec.ts` 通过公开 API 创建 21 名教师，验证账号 20+1 分页、跨页关联和再次编辑，不替换真实业务响应。

`pagination.spec.ts` 在 HTTP 边界提供确定分页数据，验证筛选、搜索复位、候选保留和列表故障重试。`auth-reliability.spec.ts` 连接真实认证及写入，只在 HTTP 交付边界注入待清理响应头、连接中断、损坏 JSON 和 503；通过用户界面及公开 API 核对结果，不 mock 内部模块或查询数据库。测试会创建独立账号及班级，建议使用本地测试环境。截图输出到 `test-results/visual/`。

## 学生作答扩展

学生考试列表、详情和作答分别由 `StudentExamsView`、`StudentExamDetailView`、`StudentAttemptView` 组合。`api/studentExams.ts` 对齐[迭代 3 接口契约](../docs/迭代3接口契约.md)，详情不读取题目，主动开始才使用机会。最新提交只显示收据与待判分／人工阅卷／已批改状态；提交后清空题目界面，已批改也不提前开放回看或成绩。

`features/attempts/` 按实际职责拆分：`AttemptQuestion.vue` 展示四类题和保存状态；`useAttemptWorkspace.ts` 编排读取、逐题保存、冲突反馈和交卷；`pageLease.ts` 持有按用户与作答命名的 Web Lock，通过 BroadcastChannel 协调主动接管；`answerDrafts.ts` 管理答案空值、草稿与版本；`examAvailability.ts` 提供时间和资格反馈。

页面实例标识每次加载重新生成，不放进可复制的 sessionStorage。普通刷新保留原令牌，取得浏览器写锁后恢复；复制标签页即使复制了令牌也只能只读。新浏览器或设备没有原令牌时，已激活的答卷默认只读，必须主动接管；首次自动激活携带 `expected_generation: 0`，由服务端锁内比较防止两台新设备同时抢到初始权限。主动接管释放旧页面写锁，并使用服务端新令牌代次；先读取服务器答案，放弃陈旧草稿。离开页面会停止写入，浏览器返回缓存页面时重新取得锁并确认令牌。每次加载和权限变更递增前端代次，在途响应不能修改下一代页面状态或草稿。

本地草稿以用户、考试、作答命名，并记录逐题已确认答案版本、最新输入，以及响应不确定时已发出的值与版本。重试和刷新先通过 HTTP 核对服务器版本，仍在截止前才保存；用户改回旧值或清空也保留最新意图。倒计时使用服务器 `server_now`、固定 `deadline_at` 和浏览器单调时钟展示，设备时间变化不能延长作答。交卷先同步防抖和在途保存，再列出空题确认；到期只显示服务端自动交卷事实，未上传草稿不能补传。待检查标记仅作为当前作答辅助，保存在页面会话中。

`student-attempt.spec.ts` 连接真实 PostgreSQL、Redis、API 和 worker，覆盖开始、四类答案、刷新、固定截止时间、防抖交卷、空题确认、复制页接管、响应丢失及离线恢复、截止拒绝、版本冲突、资格撤销和整场取消。故障只在浏览器网络或公开 HTTP 交付边界注入。保持单 worker，并指定独立输出目录，避免多个测试进程争用产物：

```bash
PLAYWRIGHT_EXTERNAL_SERVER=1 npm run test:e2e -- tests/e2e/student-attempt.spec.ts --workers=1 --output=../.local/iteration3-frontend/check --reporter=list
```

运行前按上文从 `.local/e2e.env` 加载私有凭据，不将凭据或本地报告提交到仓库。

## 自动判分与人工阅卷

`api/grading.ts` 对齐[迭代 4 接口契约](../docs/迭代4接口契约.md)，集中定义答卷、任务、单题评分、历史和最终成绩的类型。`GradingTasksView` 提供我的任务、待指派、完成与全部任务；管理员默认待指派，教师默认自己的任务。考试详情中的答卷与成绩区域按需挂载 `ExamAttemptList` 或 `ExamFinalResults`，保留服务端分页与学生搜索。最终成绩先选择最后一次有效提交；该次待批改时不展示此前成绩。

`StaffAttemptView` 组合整卷概览、题目导航、答案与评分表单。`features/grading/useGradingWorkspace.ts` 编排整卷读取和逐题保存；评分成功以服务端完整答卷更新单题、任务、权限与总分。`GradeForm` 只处理分值、评语、改分原因和未保存状态；首次整卷完成前的指定教师权限直接使用 API 的 `can_grade`。版本冲突保留输入并阻止旧版本重试，明确确认后重新读取。纯客观题或全空简答不显示首阅限制。

`GradingHistory` 按需读取单题历史；`ReassignTask` 为管理员提供分页激活教师候选和必填改派原因。`StandardCorrection` 仅编辑标准答案、简答依据、解析与更正原因，题干、选项和分值仍锁定；重判中的旧题分清楚标注为旧依据评分。`WithdrawResults` 提供先撤回再更正的入口，`features/results/PublishResults.vue` 提供独立的整场公布操作，前置检查以服务端为准。

`grading-workspace.spec.ts` 通过真实公开 HTTP 创建独立教师、学生、快照与提交，浏览器验证整卷首阅、后续改分、并发冲突、历史、停用改派、依据更正、最终成绩和学生收据可见性。测试不访问数据库或 mock 内部模块，后台正常运行；本地证据统一输出到 `.local/iteration4-frontend/`，不提交凭据与运行产物。

## 迭代 5 阶段实现

`api/results.ts`、`mistakes.ts`、`analytics.ts` 集中定义结果与统计契约。`features/results/` 负责结果状态、快照展示和当前页面敏感数据请求；每次重读先清空旧结果，取消旧请求，并阻止过期响应恢复已隐藏内容。历史、错题使用服务端筛选分页，不在全局 store 缓存成绩或标准答案。

`features/analytics/` 拆分教师统计面板、图表选项与 ECharts 运行时；图表按需加载柱形／折线和 SVG 渲染器，无样本显示空态，公开考试不显示虚构应考分母。

2026-10-09 按用户要求暂停：学生分析页面尚未实现，相关待实现浏览器场景标记 `fixme`，不代表测试通过。已完成切片的真实红绿证据与后续工作保存在本地 `.local/iteration5-frontend/handoff.md` 及 `docs/迭代5验证记录.md`；整轮仍待组合回归与桌面／手机完整验收，`docs/` 不再由 Git 追踪。
