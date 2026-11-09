# 日常运维与故障恢复指南

**中文** | [English](operations.en.md)

本文档面向负责系统部署、数据库升级、数据备份与异常恢复的运维与管理人员，用清晰的操作步骤讲透 **服务怎么启停、数据库怎么安全升级、Redis 或 Worker 挂了怎么兜底，以及管理员忘了密码怎么恢复**。

---

## 一、服务进程职责与启停顺序

系统的持久化数据全部存放在 **PostgreSQL** 中；**Redis** 负责保存登录会话（Session）和 ARQ 异步任务队列。应用层分为 **后端 API**、**后台 Worker** 和 **前端页面** 三个独立进程运行。

### 容灾设计原则（为什么不用慌？）
- **Worker 挂了或队列投递失败，答案绝对不会丢**：学生已经保存的答案全部落盘在 PostgreSQL 里。一旦 Worker 重启或执行手动补偿命令，系统会自动扫描数据库里积压的待办记录并补齐收卷、判分和派单。
- **Redis 挂了，安全绝不降级**：如果负责认证的 Redis 不可用，API 会安全拒绝受保护的操作（返回 `503 AUTH_SERVICE_UNAVAILABLE`），绝不会降级变成“免登录裸奔”。

### 标准启停顺序
- **启动顺序**：`PostgreSQL 与 Redis` → `Alembic 数据库迁移` → `后端 API 与 ARQ Worker` → `前端服务`
- **停止顺序**：`停止接收新请求并关前端` → `按 Ctrl+C 或通过进程管理器停掉 API 与 Worker` → `正常关闭本项目专用的 Redis 与 PostgreSQL`
- **配置一致性**：API 与 Worker 进程的 `DATABASE_URL`、`ARQ_REDIS_URL`（未单独配置时默认使用 `REDIS_URL`）和 `ARQ_QUEUE_NAME` 必须完全一致。
- **健康检查说明**：`/api/health` 返回 `ok` 只代表 API 进程还活着，不代表数据库和 Redis 一定正常。验收环境是否就绪，请实际测试一次登录、业务列表读取并观察 Worker 日志。

---

## 二、数据库升级与回滚

当前数据库迁移脚本从 `0001` 递增到 `0018`（最新版本号以 `alembic heads` 输出为准）。
> 其中：`0016` 新增运行日志表与全局日志设置，`0017` 为已提交审计记录增加稳定读取序号，`0018` 为待发布审计记录增加部分索引以避免全表扫描。

### 1. 常用迁移检查与升级命令
在 `backend/` 目录下执行（会自动读取当前环境的 `DATABASE_URL`）：

```bash
uv run alembic current       # 查看当前数据库所处的迁移版本
uv run alembic heads         # 查看代码库中最新的目标版本
uv run alembic history       # 查看完整迁移历史
uv run alembic upgrade head  # 将数据库升级到最新版本
uv run alembic check         # 检查代码中的 ORM 模型与数据库表结构是否完全一致
```

### 2. 生产库升级四步安全法则
在对已有业务数据的数据库执行升级前，请严格遵循以下顺序：
1. 记录当前的 Git Commit 哈希值和 `alembic current` 版本号。
2. 暂停前端入口、停止 API 写入与后台 Worker。
3. **完整备份 PostgreSQL 数据库和题目图片上传目录（`ASSET_STORAGE_DIR`）**。
4. 先把备份恢复到一个临时副本库上试跑一次 `alembic upgrade head`，确认无误后，再对正式业务库执行升级。（注意：应用启动时不会自动建表或清库，也 **严禁** 用 `alembic stamp` 假装执行过迁移）。

### 3. 关于版本回滚（Downgrade）的警告
**数据库降级（`downgrade`）不等于无损撤销！** 降级脚本可能会直接 `DROP` 掉新版本新增的表、字段、索引以及里面的数据（例如降级到 `0015` 会移除 `0016` 新增的运行日志表，但原有的业务审计表仍保留）。

- **严禁在有重要数据的业务库上执行 `downgrade base`**。
- 如果线上升级后发现严重不兼容，**最安全的做法是用升级前的备份恢复到一个新库，并将代码切回对应的旧版本**；只有当你仔细读过目标迁移脚本的 `downgrade()` 函数、确认不会误删需保留的业务数据时，才允许原地执行 `downgrade`。
- 如果你只是想在开发测试阶段验证迁移脚本的“升级 → 降级 → 再升级”往返逻辑，**必须先把 `DATABASE_URL` 指向一个新建的、可随时丢弃的空库**，再执行：
  ```bash
  uv run alembic upgrade head
  uv run alembic downgrade 0014
  uv run alembic upgrade head
  uv run alembic check
  ```

---

## 三、数据备份与恢复

### 1. 备份必须包含哪几样东西？
一次完整的备份至少要包含：
1. **PostgreSQL 数据库全量备份**。
2. **`ASSET_STORAGE_DIR` 指向的完整题目图片目录** （注意：历史考试快照可能引用了老图片，千万不要只看当前题库里没引用就去删图片文件）。
3. **`.env` 环境配置的安全副本**，以及当时对应的 **Git 代码提交号与 Alembic 版本号**。
> 备份文件中包含师生个人信息、答卷和凭据，请务必妥善设置文件访问权限，切勿提交到 Git。

### 2. 推荐使用 `pg_dump` / `pg_restore`
建议使用 PostgreSQL 原生工具导出 `custom` 压缩格式备份。为了安全，请通过 PostgreSQL 的 `PGSERVICE` 服务配置或 `.pgpass` 密码文件提供凭据，**不要把带明文密码的连接串直接写在命令行参数里** （另外注意：应用 `.env` 里的 `postgresql+asyncpg://` 是给 Python 用的，不能直接塞给 `pg_dump`）：

```bash
# 1. 导出备份（假设已在 pg_service.conf 中配好源库服务名）
pg_dump --format=custom --file=exam-backup.dump

# 2. 恢复到新建的空库（service=exam_restore 指向预先建好的空恢复库，避免直接覆盖源库）
pg_restore --dbname='service=exam_restore' --no-owner --no-privileges exam-backup.dump
```

恢复完数据库后，同步还原图片目录，核对代码版本与迁移版本，并实际登录系统检查题目图片、答卷和成绩是否正常，**不要只看 `.dump` 文件存在就以为备份可用**。

- **关于 Redis 备份**：Redis 即使丢了数据也不会丢业务事实——队列丢了靠 Worker 扫描 PostgreSQL 自动恢复，会话丢了最多让用户重新登录一次。如果把生产备份恢复到演练环境做测试，请务必使用独立的 Redis 实例、独立端口和独立的图片目录副本，防止污染生产环境。

---

## 四、Worker 常驻与队列故障手动恢复

### 1. 正常启动常驻 Worker
```bash
cd backend
uv run arq app.workers.attempts.WorkerSettings
```
Worker 启动后会立即恢复积压任务，随后每 30 秒自动扫描一次数据库（默认每批处理 100 条，可通过环境变量 `ATTEMPT_SCAN_BATCH_SIZE` 在 `1 ~ 1000` 之间调整）。所有自动交卷、客观题判分和阅卷派单都会实时核对状态、资格与修订版本号，重复执行是幂等安全的，不会把已作废的答卷复活，也不会覆盖老师新改的评分标准。

### 2. 当 Redis 队列彻底不可用时的应急手动恢复
万一考试刚结束时 Redis 故障且一时半会儿修不好，你可以绕过 Redis，直接在 `backend/` 下运行 **纯依赖 PostgreSQL** 的手动补偿命令：

```bash
# 第一步：把到期的答卷批量自动收卷
uv run python -m app.workers recover-attempts --limit 100

# 第二步：把已交卷的客观题批量判分，并在整场考完后分配主观题阅卷任务
uv run python -m app.workers recover-grading --limit 100
```

- 查看命令输出的 JSON：如果 `failed` 不为 0，请排查报错原因后重试；如果待办超过 100 条，可多跑几次直到处理完毕。
- **边界说明**：自动补交卷只能使用截止时间前已经保存到服务器的答案；如果某场考试没有可用的激活阅卷教师，重跑 Worker 也没法凭空派单，需要管理员登录后台把任务 **改派** 给其他在岗教师。

---

## 五、管理员与会话恢复

### 1. 管理员忘记密码怎么办？
普通教师和学生忘了密码，由管理员人工核验身份后在后台页面点“重置密码”生成临时密码即可。

如果 **系统管理员自己忘了密码**，请按以下步骤在服务器上重置：
1. 打开服务器受保护的 `backend/.env` 文件，核对 `ADMIN_LOGIN_NAME`，并将 `ADMIN_PASSWORD` 修改为新的强密码（切勿把密码直接写在命令行参数里）。
2. 在 `backend/` 目录下运行：
   ```bash
   cd backend
   uv run python -m app.cli reset-admin
   ```
3. 该命令会更新数据库中的管理员密码、将 `auth_version` 认证版本号加 1，并立即吊销旧的登录会话。修改完 `.env` 后如涉及其他配置变更，记得重启读取该配置的进程。

### 2. 会话清理补偿命令（`X-Session-Cleanup: pending`）
当修改密码或停用账号已经在 PostgreSQL 提交成功，但当时 Redis 恰好网络闪断没能立刻删掉旧 Session 键时，接口仍会返回成功，并附带响应头 `X-Session-Cleanup: pending`（此时无需重复提交表单，数据库里的 `auth_version` 已经能拦住旧会话了）。等 Redis 恢复正常后，可运行以下命令清理残留会话：

```bash
cd backend
uv run python -m app.cli retry-session-cleanups --limit 100
```
命令会输出 `attempted`、`completed`、`pending`、`failed` 统计，若 `pending` 仍大于 0 可继续执行直至清零。

---

## 六、常见问题排查速查表（FAQ）

管理员日常可通过后台 **[系统日志](logging.md)** 页面排查运行报错与审计记录。如果服务压根没启动起来、进不去后台页面，请直接在前台终端运行 API 或 Worker 查看报错输出。

| 遇到的现象 | 原因分析与排查步骤 |
| :--- | :--- |
| **点登录后还是停在登录页 / 提示接口连不上** | 1. 检查后端 API、Vite 代理和 Redis 是否都已启动；<br>2. **检查浏览器地址栏是否混用了 `localhost` 和 `127.0.0.1`** （两边必须统一）；<br>3. 若是生产环境，检查 HTTPS 与 `COOKIE_SECURE=true` 配置是否匹配。 |
| **学生能登录，但进不去考试工作台** | 检查该学生是否还处于 **“待审核”** 状态、账号是否被停用，或者是否处于首次登录 **强制修改临时密码** 阶段。 |
| **考试时间到了，答卷却一直停在“作答中/待处理”** | 检查后台 ARQ Worker 进程是否在跑，且 `REDIS_URL` / `ARQ_QUEUE_NAME` 是否与 API 完全一致；也可直接运行上文的 `recover-attempts` 和 `recover-grading` 手动补偿。 |
| **考试结束了，阅卷任务却一直显示“待指派”** | 说明该考试原先指定的阅卷教师已被停用或当前无可用教师。请用管理员账号进入该场考试的“阅卷进度与成绩”，点击 **“改派任务”** 转交给在岗教师。 |
| **学生交完卷很久了，还是看不到成绩** | 依次检查：1. 整场考试时间是否已结束；2. 所有有效答卷（含主观题）是否已全部批改完；3. 教师是否点击了 **“公布结果”** （或是否正在撤回更正中）。 |
| **学生能看到总分，但点不开答卷回看和错题** | 这是正常权限控制：检查教师在该场考试设置里是否关闭了 **“允许考后回看”** 开关。 |
| **保存题目或评分时弹窗提示“版本冲突”** | 说明在你编辑期间，另一位老师刚刚修改并保存了同一条数据。请刷新页面读取最新内容、核对差异后再提交，不要强行重发旧请求。 |

---

## 七、正式生产环境部署红线

1. **网络与认证安全**：生产环境必须全站启用 **HTTPS**，设置 `ENVIRONMENT=production`、`COOKIE_SECURE=true`，更换大于 32 位的独立随机 `JWT_SECRET`，并将 `CORS_ORIGINS` 严格限制为真实前端域名。登录与所有写操作严禁绕过 CSRF 校验。
2. **存储与静态资源隔离**：PostgreSQL、Redis 端口严禁直接暴露到公网；题目图片目录（`ASSET_STORAGE_DIR`）严禁直接挂在 Nginx 下公开访问，必须统一走后端鉴权 API 读取。前端打包后的 `dist/` 需在 Nginx 等服务器配置 SPA History 路由回退（Fallback 到 `index.html`）并反向代理同源 `/api`。
3. **容量评估**： **[100 人并发实测报告](performance.md)** 中的性能数据仅代表单机本地测试环境下的表现。在正式上生产大考前，请务必在目标服务器硬件和真实网络环境下重新执行压测验证。
