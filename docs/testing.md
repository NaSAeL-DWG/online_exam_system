# 测试与验证指南

本项目坚持 **测试驱动开发（TDD）** 与 **真实环境验证**。

简单来说，我们的测试有两条铁律：
1. **先红后绿**：新增或修改公开行为时，先写一个会失败的测试，再写实现代码让它通过。
2. **拒绝用假存储自欺欺人**：除了极少数纯数学计算（如多选题集合判分、`Decimal` 四舍五入）可以用纯函数单测外，**所有核心测试都直接跑在真实的 PostgreSQL、真实的 Redis 和真实的 Chromium 浏览器上**——绝不用 SQLite 内存库去冒充 PostgreSQL 的行级锁（`FOR UPDATE`）、JSONB、唯一约束和时区行为。

---

## 一、后端测试与代码检查

### 1. 准备隔离的测试数据库与 Redis
> **安全警告：测试会建表、写数据、模拟故障清理，千万不要把测试连接指向你的日常开发库或生产业务库！**

请在本地专门建一个空的 PostgreSQL 测试库（例如 `exam_test`），并选一个独立的 Redis DB 编号（例如 `15`）。将连接信息保存在已被 Git 忽略的私有文件 `.local/backend-test.env` 中：

```bash
# .local/backend-test.env 示例格式
TEST_DATABASE_URL="postgresql+asyncpg://用户:密码@127.0.0.1:55432/exam_test"
TEST_REDIS_URL="redis://:密码@127.0.0.1:16379/15"
```

### 2. 按改动范围运行 Pytest
不需要每次改一行代码都把全量测试跑一遍，**请根据你修改的模块精准选择对应的测试文件**：

```bash
cd backend
uv sync --locked --python 3.13

# 加载私有测试环境变量（不打印密码到终端）
set -a
source ../.local/backend-test.env
set +a

# 示例：如果你改了成绩与学习分析模块，就跑对应的 API 集成测试
uv run python -m pytest -q tests/test_results_api.py tests/test_analytics_api.py
```

**测试类型说明：**
- 如果你改了 **学生作答 (`attempt`) 或阅卷 (`grading`)**，请务必跑上对应的并发锁、权限边界或独立 Worker 恢复测试。
- 大多数 `test_*_api.py` 通过进程内 ASGI 客户端直接调用真实数据库和 Redis；文件名带 `recovery` 的可靠性测试则会真实拉起独立的 API / Worker 子进程来验证崩溃恢复。

### 3. 静态代码检查与迁移一致性检查
每次提交后端代码前，运行 Ruff 代码检查与 Alembic 模型对比：

```bash
uv run ruff check app tests
uv run alembic check
```

> **提示**：运行 `alembic check` 前，需要先确保当前环境变量指向的开发库或测试库已经执行过 `uv run alembic upgrade head`，否则它会提示数据库版本落后。如果你想测试迁移脚本的“升级 → 降级 → 再升级”往返是否无误，请务必在一个 **新建的、可随时丢弃的空库** 里操作，详见 **[日常运维与故障恢复：数据库升级与回滚](operations.md#数据库升级与回滚)**。

---

## 二、前端构建检查与 Playwright 浏览器测试

### 1. 启动被测环境与准备凭据
Playwright 端到端（E2E）测试需要连接真实运行的后端 API、ARQ Worker、PostgreSQL 和 Redis（测试过程中会自动通过公开 API 创建带唯一标识的测试账号、试卷、考试和答卷，**严禁对着生产环境跑 E2E 测试** ）。

先在 `.local/e2e.env` 中配好测试环境的管理员账号密码：

```bash
# .local/e2e.env 示例格式
E2E_ADMIN_LOGIN="admin"
E2E_ADMIN_PASSWORD="你的测试管理员密码"
```

### 2. 运行端到端测试与构建检查

```bash
cd frontend
npm ci
npx playwright install chromium

# 加载 E2E 环境变量
set -a
source ../.local/e2e.env
set +a

# 按你修改的业务范围运行对应的 spec 用例（以下为成绩工作台示例）
npm run test:e2e -- tests/e2e/results-workspace.spec.ts

# 类型检查、生产打包验证与代码格式检查
npm run build
npm run format:check
```

**Playwright 运行小贴士：**
- 默认访问地址为 `http://127.0.0.1:5173`。如果你已经在外部手动启动了前端服务，可以加上 `PLAYWRIGHT_EXTERNAL_SERVER=1` 直接复用，也可以用 `PLAYWRIGHT_BASE_URL` 指定其他端口（注意该地址必须配置好同源 `/api` 后端代理，不能只起一个纯静态文件服务）。
- **测试写什么、不写什么**：浏览器测试重点验证用户真正关心的可观察行为——比如自动保存与多标签页接管、未答题交卷确认、成绩公布与撤回后的即时隐藏、角色路由拦截、网络异常恢复等。不要去写“测某个内部组件变量值”的脆弱单测。
- **双端视觉目检**：涉及页面布局改动时，需同时在桌面宽度（1440px / 1280px）和手机宽度（390px）下检查，不仅要断言没有整页横向溢出，还要人工目检生成的截图是否美观、对齐。

---

## 三、专项验收命令速查（以日志系统为例）

如果你修改了系统日志、操作审计或架构契约，可以运行以下专项验证命令：

```bash
# 1. 后端日志接口与架构契约检查（在 backend/ 目录下，先加载 .local/backend-test.env）
uv run python -m pytest -q tests/test_logging_api.py tests/test_architecture_contract_api.py

# 2. 后端日志高负载容量与轮转独立验收
uv run python -m pytest -q tests/test_logging_acceptance_api.py

# 3. 前端管理员日志页面 E2E 验证（在 frontend/ 目录下，先加载 .local/e2e.env 并启动服务）
npm run test:e2e -- tests/e2e/system-logs.spec.ts
```

> **关于 `test_logging_acceptance_api.py` 的环境要求**：
> 该验收用例会真实灌入超过 100,000 条运行日志来测试容量自动清理，并拉起 4 个并发进程写入约 74 MiB 日志文件来验证 `10 MiB × 5` 文件轮转。同时，为了模拟“数据库写入权限丢失时不拖垮正常业务”的极端场景，测试数据库连接账号需要具备创建和清理临时数据库角色（Role）的权限（这只是跑这条极端验收测试的要求，日常部署应用不需要此权限）。

---

## 四、测试报告与产物管理规范

1. **如实记录验证证据**：记录你实际跑过的命令、环境版本、报错原因、修复后的通过结果以及尚未覆盖的边界。不同批次的重复子集测试不要简单相加凑“通过总数”；100 人并发压测有专门的脚本和报告要求，详见 **[100 人并发实测报告](performance.md)**。
2. **敏感产物绝不入库**：测试生成的 HTML 报告、截图、Playwright trace 轨迹文件以及 `.local/*.env` 私有配置一律保存在 `.local/` 或已被 `.gitignore` 忽略的目录中。报错日志里可能带有测试配置或敏感输入，对外分享结论前请先脱敏。
