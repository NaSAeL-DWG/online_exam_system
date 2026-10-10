# 快速启动

下方手动安装命令使用 Bash，Windows 可使用 Git Bash；完成首次配置后也可用 PowerShell 快速启动。PostgreSQL、Redis、API、worker 和前端独立运行，不依赖 Docker。

## Windows 快速启动

已经安装依赖、填写 `backend/.env` 并迁移数据库后，在项目根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1
```

脚本会检查依赖和迁移版本，按顺序启动 PostgreSQL、Redis、API、worker 和前端，再验证数据库读取、Redis、后端及前端代理。已经运行的服务直接复用，其他应用占用端口时明确报错。成功后访问 `http://127.0.0.1:5173`。

该入口适用于当前 Windows／WSL 本地开发布局：数据库配置使用本机地址，应用端口为 18000／5173。未运行的 PostgreSQL 使用项目 `.local/pgdata`；未运行的 Redis 使用 WSL `Ubuntu-24.04` 和私有 `.local/redis.conf`。这两个目录／文件需提前初始化，脚本不会创建凭据、清库、安装依赖或自动迁移。

PostgreSQL 的 `pg_ctl.exe` 优先从 PATH 查找，当前机器也支持 `D:\postgresql\bin\pg_ctl.exe`；其他安装路径可追加 `-PgCtl 'C:\实际路径\pg_ctl.exe'`。后台进程使用隐藏窗口，日志放在 `.local/services/`，运行记录在 `.local/service-state.json`，不纳入 Git。通过会回收子进程树的自动化终端运行时追加 `-KeepAlive`，让启动宿主保持存活；普通交互式 PowerShell 无需此开关。

## 1. 准备环境

已验证的环境为 Python 3.13、uv 0.10、Node.js 24、PostgreSQL 18、Redis 8。以 `backend/uv.lock` 和 `frontend/package-lock.json` 安装锁定依赖。Windows 的 Redis 可在 WSL 中运行，确保 Windows 可访问其监听地址。

先创建属于本项目的 PostgreSQL 数据库及有迁移权限的账号，并启动启用认证的 Redis。本地示例端口为 PostgreSQL 55432、Redis 16379、API 18000、前端 5173；已有实例可以使用其他端口。不要直接复用测试库作为业务库。

## 2. 后端配置与迁移

从仓库根目录执行：

```bash
cd backend
uv sync --locked --python 3.13
# 仅第一次创建；已有 .env 时保留现有文件。
test -f .env || cp .env.example .env
```

编辑 `backend/.env`，至少替换以下值：

| 变量 | 用途 |
|---|---|
| `ENVIRONMENT` | 本地使用 `development`，测试为 `test`，正式部署为 `production` |
| `DATABASE_URL` | `postgresql+asyncpg://用户:密码@地址:端口/库名`；密码中保留字符须进行 URL 编码 |
| `REDIS_URL` | Redis 认证与会话地址，默认也用于后台队列 |
| `JWT_SECRET` | 至少 32 字符的独立随机密钥；替换示例字符串 |
| `ADMIN_LOGIN_NAME`、`ADMIN_PASSWORD` | 首次初始化管理员的账号和强密码 |
| `ADMIN_REAL_NAME`、`ADMIN_EMAIL`、`ADMIN_PHONE_NUMBER` | 管理员资料 |
| `CORS_ORIGINS` | 实际前端来源，例如 `http://127.0.0.1:5173` |
| `ASSET_STORAGE_DIR` | 持久图片目录；相对路径以启动后端时的工作目录为基准 |

本地 HTTP 使用 `COOKIE_SECURE=false`。正式部署必须使用 HTTPS、`ENVIRONMENT=production` 和 `COOKIE_SECURE=true`。`.env` 被 Git 忽略，不把真实值写入示例文件或 shell 历史中的命令参数。

```bash
uv run alembic upgrade head
uv run python -m app.cli init-admin
uv run uvicorn app.main:app --host 127.0.0.1 --port 18000
```

管理员由命令初始化；网页没有创建管理员入口。`init-admin` 不覆盖已有管理员的密码。更换环境中的密码不会自动修改数据库账号，重置流程见[运维指南](operations.md#管理员与会话恢复)。

## 3. 启动独立 worker

新开终端，在仓库根目录执行：

```bash
cd backend
uv run arq app.workers.attempts.WorkerSettings
```

API 与 worker 必须使用同一数据库及队列。`ARQ_REDIS_URL` 未设置时沿用 `REDIS_URL`；若设置，两个进程须使用同一 `ARQ_REDIS_URL` 与 `ARQ_QUEUE_NAME`。worker 负责到期交卷、客观题判分与人工任务分配，启动即补处理数据库持久待办，此后每 30 秒扫描一次。

## 4. 启动前端

再新开终端：

```bash
cd frontend
npm ci
# API 地址与默认值不同时，再创建 .env 并设置 VITE_API_TARGET。
npm run dev
```

默认 Vite 将 `/api` 请求代理到 `http://127.0.0.1:18000`。打开 `http://127.0.0.1:5173`，全程使用同一主机名，不在 `localhost` 与 `127.0.0.1` 之间切换，以免 Cookie 不一致。

## 5. 检查与使用

- `http://127.0.0.1:18000/api/health` 与 `http://127.0.0.1:5173/api/health` 均应返回 `{"status":"ok"}`。这只是进程与代理检查，成功登录才覆盖数据库、Redis 与认证配置。
- 用初始化管理员登录，创建教师。教师以临时密码首次登录后必须修改密码。
- 学生自行注册，教师审核通过后才能参加考试。完整流程见[角色操作指南](user-guide.md)。

结束使用时先停止 Vite、API 和 worker，再正常关闭本项目的 Redis/PostgreSQL，保留数据目录。不要关闭其他项目共用的数据库服务。生产构建使用 `cd frontend && npm run build`；`dist/` 需要静态服务器的 SPA 回退及同源 `/api` 反向代理，Vite 开发服务器不是生产部署方案。
