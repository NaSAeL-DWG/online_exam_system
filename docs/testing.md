# 测试与验证

默认使用 TDD：一个公开行为先失败，再实现到通过。主边界为真实 PostgreSQL/Redis 的 HTTP API 和真实浏览器；不要使用 SQLite 替代锁、JSONB、唯一约束和时区验证。纯判分集合与 Decimal 舍入可以采用少量纯函数测试。

## 后端

准备专用测试数据库和 Redis DB，连接必须与开发及业务数据隔离。测试会迁移数据库、建立账号和业务记录；Redis 故障／清理场景也可能操作专用实例。凭据放在忽略的私有配置文件中，内容格式为 shell 环境变量，不打印完整配置。

```bash
cd backend
uv sync --locked --python 3.13
# 私有文件由操作者创建：至少包含 TEST_DATABASE_URL、TEST_REDIS_URL。
set -a
source ../.local/backend-test.env
set +a
uv run python -m pytest -q tests/test_results_api.py tests/test_analytics_api.py
```

选文件应跟随实际改动，以上只是结果模块示例。作答或阅卷改动需要对应的并发、权限或独立 worker 场景。多数 API 测试使用进程内 ASGI 入口和真实存储；名称含 recovery 的可靠性测试启动独立 API/worker 进程。不要把前者描述为网络吞吐压测。

```bash
uv run ruff check app tests
uv run alembic check
```

`alembic check` 检查模型和数据库迁移差异，需要先对目标开发／测试库 `upgrade head`。迁移往返请在新建可重建的空库执行，详见[运维指南](operations.md#数据库升级与回滚)。

## 浏览器

先启动独立的测试／开发 API、worker、数据库与 Redis，初始化管理员。浏览器测试会通过 API 创建唯一标识的账号、考试与答卷，不应用于生产环境。

```bash
cd frontend
npm ci
npx playwright install chromium
set -a
# 私有配置至少设置 E2E_ADMIN_LOGIN、E2E_ADMIN_PASSWORD。
source ../.local/e2e.env
set +a
npm run test:e2e -- tests/e2e/results-workspace.spec.ts
npm run build
npm run format:check
```

默认测试访问 `http://127.0.0.1:5173`，Playwright 可启动或复用 Vite。已有外部服务时设置 `PLAYWRIGHT_EXTERNAL_SERVER=1`；可用 `PLAYWRIGHT_BASE_URL` 调整地址。测试通常还需要同源 `/api` 代理，不能只提供静态页面。

浏览器断言优先验证可观察行为：保存与接管、未答题确认、结果公布和撤回、角色导航、错误恢复等。不为每个颜色或内部组件状态创建单元测试。重要页面同时检查桌面和 390 px；截图需目检，宽度断言不能替代视觉审核。

## 证据与范围

记录执行命令、版本、环境、失败原因、修复后结果及未覆盖范围。最终组合与重复定向子集不累加通过数量。并发容量需要独立记录硬件、数据量、会话数、负载方式、错误率和延迟，不能拿 `/health` 或登录并发替代完整作答流程。

报告、截图、trace 和私有配置保留在 `.local/` 或工具已忽略的输出目录。公开记录只保留脱敏结论；失败日志可能包含敏感输入，分享前检查。`tech-docs/` 是本地开发证据，`docs/` 只发布可复现的项目使用与维护说明。
