# 局域网 HTTP 作答页面白屏

日期：2026-11-16。环境：开发服务器 Docker Compose，浏览器通过 HTTP IP 地址访问。

## 现象与证据

- 本机开发环境正常，服务器登录页正常；登录学生进入 `/student/attempts/:id` 后只剩“跳至主要内容”。入口 HTML、前端模块均能正常加载，容器正在运行。
- 使用 Playwright 加载服务器实际构建资源，并拦截身份与答卷接口隔离业务数据，稳定复现 `TypeError: crypto.randomUUID is not a function`。
- 同一地址的能力检测结果：`isSecureContext=false`、`crypto.randomUUID=undefined`、`navigator.locks=undefined`；`crypto.getRandomValues` 和 `structuredClone` 可用。
- 仅在诊断浏览器补上 UUID 方法后页面恢复渲染，排除入口资源与路由回退问题。
- 原报告中的答卷已到截止时间，数据库状态为 `SUBMITTED / GRADED`，页面令牌代次为 0。诊断与修复不修改该答卷、答案或考试时间。

## 根因与修复

页面租约初始化直接调用仅限安全上下文的 `crypto.randomUUID()`，导致 Vue setup 中断。只修复 UUID 仍不足以在 HTTP 下作答：原租约实现会在缺少 Web Locks 时拒绝获得写权限。

1. 页面与选择题选项统一使用 `createClientId()`；优先调用原生 UUID，缺失时通过 `crypto.getRandomValues` 生成符合 UUID v4 格式的标识。
2. 有 Web Locks 时保留原独占锁流程。缺少 Web Locks 时允许向服务端请求首次激活，由 `expected_generation=0` 防止并发页面自动接管。
3. 无 Web Locks 时不复用 sessionStorage 中的页面令牌。刷新或复制页面后先保持只读，用户明确接管后才生成新代次并读取服务器答案；BroadcastChannel 通知旧页面停止写入，后端继续校验每次保存与交卷的令牌、代次。

HTTP 兼容模式刷新后需主动接管，接管不会合并旧页面尚未上传的草稿。正式部署仍按运维规范使用 HTTPS。

## 验证

定向回归命令（在 `frontend/` 下执行）：

```bash
npx playwright test tests/e2e/c3-student.spec.ts -g '缺少原生 randomUUID|HTTP 缺少 Web Locks' --reporter=list
```

修复前两项均失败：一项没有标题与题面，另一项选项始终禁用。修复后两项通过，覆盖首次保存、复制令牌不能自动写入、主动接管、旧页停止写入及刷新后重新确认权限。

补充覆盖：缺少原生 UUID 时创建选择题、追加选项，并检查提交的三个选项 ID 均为不同的合法 UUID v4。

- TypeScript 检查、Vite 正式构建及变更文件 Prettier 检查通过。
- 部署后，以服务器真实 HTTP 资源运行 `c3-student.spec.ts` 与 `content-admin-pages-design.spec.ts`，14 项全部通过；这些回归使用固定接口快照，不修改服务器业务数据。
- 另为原答卷所属学生建立短期诊断会话，使用真实身份与真实答卷 GET 接口验证：接口返回 200，显示“本次作答已提交”，控制台错误为 0，答卷写请求为 0。验证后已撤销诊断会话并清除本地令牌。
- 同次修复阅卷任务空状态缺少留白的问题；服务器页面在 1440px 和 390px 下均显示 1px 卡片边框及 `48px 24px` 内边距，无整页水平溢出。

## 部署与回退

开发服务器源码目录为 `/root/onlineexamsystem`，此次仅替换 `web` 容器，API、Worker、数据库及 Redis 保持运行。修复源码已同步；前端构建产物在本地生成后打包为可重启保留的 Docker 镜像。

- 当前前端镜像：`online-exam-system-web:http-attempt-fix-20261116`，同时标记为 Compose 使用的 `latest`。
- 旧容器快照：`online-exam-system-web:before-http-attempt-fix-20261116`；部署前已有的另一构建镜像保留为 `online-exam-system-web:previous-build-20261116`。
- 源文件备份：`.deletedfiles/http-attempt-fix-20261116-223651/sources-before.tar.gz`。
- 补丁及构建产物：`.local/http-attempt-fix-20261116-223651/`。镜像保留旧哈希资源，已打开的页面仍能加载原来的延迟模块。

如需紧急回退页面，在服务器源码目录执行以下命令；后续重新构建前还需从备份恢复对应源码：

```bash
docker image tag online-exam-system-web:before-http-attempt-fix-20261116 online-exam-system-web:latest
docker compose --env-file docker/.env -f docker/compose.yaml up -d --no-build --no-deps web
```
