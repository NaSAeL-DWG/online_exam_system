# 快速启动指南

**中文** | [English](quick-start.en.md)

本文档带你从零把 **在线限时考试系统** 在本地跑起来。

整个系统 **不需要 Docker**，本地运行包含 5 个部分：**PostgreSQL 数据库**、**Redis 缓存/队列**、**FastAPI 后端接口**、**ARQ 后台 Worker** 和 **Vite 前端页面**。

> **终端提示**：下方的手动配置命令默认使用 Bash 语法（Windows 用户推荐使用 Git Bash）。当你完成第一次环境配置和数据库迁移后，日常开发可以直接用我们提供的 PowerShell 脚本一键拉起所有服务。

---

## Windows 快速启动

如果你 **已经装好依赖、填好 `backend/.env` 并跑完数据库迁移**，日常启动不需要开一堆黑框，直接在仓库根目录运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1
```

**这个脚本会自动帮你做四件事：**
1. 检查本地命令依赖和数据库 Alembic 迁移版本是否最新。
2. 按顺序启动 PostgreSQL、Redis、后端 API（`18000` 端口）、后台 Worker 和前端 Vite（`5173` 端口）。
3. 自动复用已经在跑的同类服务；如果端口被其他无关软件占用，会明确报错提醒。
4. 做一轮完整的连通性自检（数据库读取、Redis 连接、后端健康检查、前端代理），全部通过后即可直接打开 `http://127.0.0.1:5173`。

### 脚本使用注意事项

- **本地数据目录约定**：脚本针对 Windows + WSL 本地开发布局做了适配。如果 PostgreSQL 还没启动，脚本会使用项目下的 `.local/pgdata`；如果 Redis 还没启动，会调用 WSL（`Ubuntu-24.04`）加载 `.local/redis.conf`。这两个目录/文件需要提前初始化好，脚本本身不会自动建库、清库或覆盖你的配置。
- **自定义 PostgreSQL 路径**：脚本默认从系统 `PATH` 或 `D:\postgresql\bin\pg_ctl.exe` 查找 `pg_ctl.exe`。如果你的 PostgreSQL 装在其他位置，启动时加上参数即可：
  ```powershell
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1 -PgCtl 'C:\你的路径\pg_ctl.exe'
  ```
- **日志去哪看**：基础设施与前端开发服务器的启动输出保存在 `.local/services/`，进程状态记录在 `.local/service-state.json`（均已被 Git 忽略）。后端 API 与 Worker 的运行日志直接由管理员后台的[系统日志](logging.md)页面统一管理；如果服务一启动就秒退，请按下文手动启动命令在前台运行，直接看终端报错。
- **自动化终端保活**：如果在会自动回收子进程树的自动化宿主里调用该脚本，请追加 `-KeepAlive` 参数保持宿主存活；平时在普通 PowerShell 窗口里运行不需要加。

---

## 首次安装：分步手动启动

第一次拉下代码时，请按以下 5 步完成初始化。

### 第 1 步：准备基础环境

系统已在以下版本组合下完成完整验证（依赖版本已由 `backend/uv.lock` 和 `frontend/package-lock.json` 严格锁定）：

- **Python**: `3.13` + 包管理器 **uv** `0.10`
- **Node.js**: `24` + **npm**
- **PostgreSQL**: `18`
- **Redis**: `8`（Windows 下推荐在 WSL 中运行，需确保宿主机能访问其监听端口）

**你需要提前准备好：**
1. 在 PostgreSQL 中创建一个专门给本项目用的空数据库（ **千万不要拿跑单测的测试库当日常业务库用** ），并配好具备建表迁移权限的账号。
2. 启动开启了密码认证的 Redis 实例。
3. **端口参考**：本地示例通常使用 PostgreSQL `55432`、Redis `16379`、后端 API `18000`、前端 `5173`。如果你机器上已有现成实例，使用你自己的实际端口即可。

---

### 第 2 步：配置后端、迁移数据库并启动 API

在仓库根目录下打开终端，安装后端依赖并生成配置文件：

```bash
cd backend
uv sync --locked --python 3.13
# 仅在第一次没有 .env 时复制模板；已有 .env 时不会覆盖
test -f .env || cp .env.example .env
```

打开 `backend/.env`，把里面的占位符替换为你自己的真实配置：

| 环境变量 | 怎么填 | 详细说明 |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | 本地开发填 `development`，跑测试为 `test`，正式上线填 `production` |
| `DATABASE_URL` | `postgresql+asyncpg://用户:密码@地址:端口/库名` | 异步数据库连接串；**如果密码里含 `@`、`:`、`/` 等特殊字符，必须先做 URL 编码** |
| `REDIS_URL` | `redis://:密码@地址:端口/0` | 用于存登录会话，默认也兼做后台 ARQ 任务队列 |
| `JWT_SECRET` | 至少 32 位的随机字符串 | 用于签发令牌，**请务必替换掉示例里的默认字符串** |
| `ADMIN_LOGIN_NAME` | 例如 `admin` | 首次初始化系统管理员时使用的登录账号 |
| `ADMIN_PASSWORD` | 你的管理员强密码 | 首次初始化管理员的密码（长度需满 10 位） |
| `ADMIN_REAL_NAME` / `EMAIL` / `PHONE_NUMBER` | 管理员姓名、邮箱、手机号 | 管理员基础个人资料 |
| `CORS_ORIGINS` | `http://127.0.0.1:5173` | 允许跨域访问的前端地址，必须与你浏览器地址栏访问的主机名完全一致 |
| `ASSET_STORAGE_DIR` | 例如 `../.local/assets` | 题目上传图片的持久化保存目录（相对路径以启动后端时的 `backend/` 目录为基准） |
| `LOG_STORAGE_DIR` | 默认 `../.local/logs` | 服务器日志文件目录；API、Worker 和 CLI 必须指向同一个目录（仅在后台开启文件记录时写入） |

> **安全提醒**：本地 HTTP 开发时保持 `COOKIE_SECURE=false`；正式上生产环境必须启用 HTTPS，并将 `ENVIRONMENT=production`、`COOKIE_SECURE=true`。`.env` 文件已被 Git 忽略，切勿把真实密码提交到代码库或写在命令行参数里。

配置保存后，依次执行 **数据库建表迁移 → 初始化管理员账号 → 启动 API 服务**：

```bash
uv run alembic upgrade head
uv run python -m app.cli init-admin
uv run uvicorn app.main:app --host 127.0.0.1 --port 18000
```

- **关于管理员账号**：系统没有网页端“注册管理员”的入口，必须通过上面的 `init-admin` 命令创建。如果数据库里已经有这个管理员了，再次运行 `init-admin` **不会** 覆盖已有密码。万一忘了管理员密码，直接改 `.env` 是没用的，请按[运维指南：管理员密码重置](operations.md#管理员与会话恢复)执行重置命令。

---

### 第 3 步：启动后台判分与收卷 Worker

**保持刚才的 API 终端不要关**，新开第 2 个终端窗口：

```bash
cd backend
uv run arq app.workers.attempts.WorkerSettings
```

**为什么必须开 Worker？**
- 考试时间到了自动收卷、学生交卷后的客观题自动算分、以及考试结束后把简答题平均分给阅卷老师，全靠这个后台进程处理。
- Worker 启动时会立刻扫描一次数据库里积压的待办任务，之后每 30 秒巡检一次。
- **配置一致性**：API 和 Worker 必须连同一个数据库和同一个 Redis 队列（如果单独配了 `ARQ_REDIS_URL` 和 `ARQ_QUEUE_NAME`，两边必须完全相同）。

---

### 第 4 步：启动前端开发服务器

再新开第 3 个终端窗口：

```bash
cd frontend
npm ci
# 如果你的后端 API 没跑在默认的 http://127.0.0.1:18000，可新建 .env.local 设置 VITE_API_TARGET
npm run dev
```

Vite 默认会把所有 `/api` 开头的请求代理到 `http://127.0.0.1:18000`。

> **避坑重点：不要混用 `localhost` 和 `127.0.0.1`！**
> 浏览器打开 `http://127.0.0.1:5173` 后，请全程使用 `127.0.0.1`。不要一会儿用 `localhost:5173`，一会儿用 `127.0.0.1:5173`，否则浏览器的 HttpOnly Cookie 作用域对不上，会导致登录状态莫名丢失。

---

### 第 5 步：验证服务并开始使用

1. **检查服务连通性**：
   在浏览器分别打开 `http://127.0.0.1:18000/api/health` 和 `http://127.0.0.1:5173/api/health`，都返回 `{"status":"ok"}` 说明后端进程和前端代理已就绪。
2. **走通业务闭环**：
   - 用你在 `.env` 里配置的管理员账号登录 `http://127.0.0.1:5173`。
   - 在后台创建教师账号（分配临时密码）和教学班；教师首次登录系统会强制要求修改密码。
   - 学生可在登录页点击“学生注册”，提交后由教师或管理员审核通过，即可参加考试。
   - 各角色的详细使用方法，请直接阅读 **[三端角色操作指南](user-guide.md)**；想直接生成现成的丰富数据，请看 **[一键生成演示数据](demo.md)**。

---

## 停止服务与生产构建说明

- **日常停机顺序**：先在终端按 `Ctrl + C` 停掉前端 Vite、后端 API 和 Worker，再正常关闭本项目专用的 Redis 和 PostgreSQL，保留数据目录以便下次继续使用（注意不要误关你电脑上其他项目共用的数据库服务）。
- **生产环境打包**：前端生产构建执行 `cd frontend && npm run build`，生成的 `dist/` 静态文件需要配合 Nginx 等支持 SPA 路由回退（Fallback 到 `index.html`）的静态服务器使用，并将同源 `/api` 反向代理到后端服务——**切勿在生产环境直接拿 `npm run dev` 对外提供服务**。
