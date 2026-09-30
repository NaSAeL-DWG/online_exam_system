# 前端开发说明

前端使用 Vue 3、Vite、TypeScript、Naive UI、Vue Router、Pinia 和 Playwright。依赖版本已锁定在 `package-lock.json`。

## 页面结构与扩展

本轮整体重构的范围、设计要求和验证证据见[前端重构迭代](../docs/前端重构迭代.md)。前端按以下职责组织：

- `src/design/theme.ts` 与 `src/styles/`：Naive UI 主题、设计 token、共用基础样式和应用布局。页面内使用语义 token，新增样式优先放所属组件的 scoped 区域。
- `src/components/ui/`：统一页面标题、内容面板、状态徽标和 SVG 图标；不在这些基础组件中加入业务请求。
- `src/navigation/`：角色可见性、业务分组、当前模块和工作台入口。导航与首页共用模块声明，权限受限账号只显示其可用入口。
- `src/views/`：页面组合及路由入口；`src/features/`：题目编辑、试卷编排等业务状态与局部界面。复杂编辑流程按职责组合，避免将所有表单和状态塞入一个页面。
- `src/composables/usePagedList.ts`：列表页的分页、加载、失败及请求竞争处理；筛选条件和 API 调用仍由所属业务提供。
- `src/api/` 与 `src/stores/`：公开通信契约和身份状态，视觉组件不直接处理 Cookie、刷新凭据或原始 fetch。

新增后续业务时，先实现对应 API 与业务模块，在 `router.ts` 声明路由及访问条件，再在 `navigation/modules.ts` 登记实际可用的入口。导航隐藏不能替代路由和后端权限检查。尚未交付的作答、阅卷和成绩模块不显示可点击空入口。

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
