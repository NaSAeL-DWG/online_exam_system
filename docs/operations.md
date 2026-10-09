# 运维指南

## 独立进程与配置

PostgreSQL 保存业务事实；Redis 保存认证会话和 ARQ 队列。API、worker、前端分别运行。worker 丢失或队列投递失败不会删除已保存答案，恢复后通过数据库扫描补处理；Redis 认证服务不可用时 API 拒绝受保护操作，不降级为免登录。

启动顺序：数据库与 Redis → 数据库迁移 → API 与 worker → 前端。停止顺序：停止新操作与前端 → API 与 worker → 本项目专用 Redis 和 PostgreSQL。用进程管理器或前台 Ctrl+C 正常停止应用，数据库使用自身正常关闭命令。不要结束其他项目的同名进程或共用数据库实例。

`/api/health` 仅表示 API 进程存活，不证明存储可用。检查登录、实际业务读取和 worker 日志才能确认依赖正常。API 和 worker 的 `DATABASE_URL`、`ARQ_REDIS_URL`（默认沿用 `REDIS_URL`）以及 `ARQ_QUEUE_NAME` 必须一致。

## 数据库升级与回滚

当前迁移从 `0001` 到 `0015`，最终版本以 `alembic heads` 为准。命令在 `backend/` 执行并使用当前环境的连接：

```bash
uv run alembic current
uv run alembic heads
uv run alembic history
uv run alembic upgrade head
uv run alembic check
```

升级已有库之前：记录当前 Git 提交和 Alembic 版本，停止写入及 worker，备份数据库与上传目录；先在从备份恢复的副本上验证升级，再执行业务库升级。应用启动不自动建表或清空数据，不用 `stamp` 冒充迁移已执行。

回滚不等于无损撤销。降级可能删表、列、索引和其中数据；必须阅读目标迁移的 `downgrade` 并使用兼容版本的代码。以下往返只允许在**新建、可丢弃的迁移验证库**中执行，先将 `DATABASE_URL` 指向该库：

```bash
uv run alembic upgrade head
uv run alembic downgrade 0014
uv run alembic upgrade head
uv run alembic check
```

不要在有需保留数据的库上执行 `downgrade base`。业务库出现不兼容时，优先恢复备份到新库并切换到与备份匹配的代码版本；只有确认具体降级路径不损坏需保留数据时才原地回退。

## 备份与恢复

至少备份 PostgreSQL、`ASSET_STORAGE_DIR` 指向的完整图片目录、环境配置的安全副本，以及代码／迁移版本。快照可能引用历史图片，不能按当前题库引用删除文件。备份可能含个人资料、答案和凭据，应限制访问。

推荐用 PostgreSQL 原生工具生成 custom 格式备份。通过服务配置或受保护的密码文件提供连接凭据，不把含密码的 URL 放入命令参数；例如先配置 PostgreSQL `PGSERVICE`：

```bash
# PGSERVICE 指向已配置的源库服务；文件名由操作者选择。
pg_dump --format=custom --file=exam-backup.dump
# 改为已创建的空恢复库服务，避免覆盖源库。
pg_restore --dbname='service=exam_restore' --no-owner --no-privileges exam-backup.dump
```

这里的 `exam_restore` 是需事先配置的 PostgreSQL 服务名。应用连接使用 `postgresql+asyncpg://`，不能直接当成 `pg_dump` 的 libpq URL。恢复后还原图片目录，核对代码版本、迁移版本、权限和实际业务；不要只检查备份文件存在。

Redis 可以持久化以保留会话和队列，但它不能替代 PostgreSQL。队列丢失后 worker 扫描数据库恢复；会话丢失后用户重新登录。恢复生产备份后的演练实例应使用独立 Redis、端口和图片副本。

## worker 与故障恢复

常驻 worker：

```bash
cd backend
uv run arq app.workers.attempts.WorkerSettings
```

启动后立即恢复待办，此后每 30 秒扫描，默认批次 100，可用 `ATTEMPT_SCAN_BATCH_SIZE` 在 1—1000 内调整。提交、判分和分配会检查实时状态、资格与修订号，重试不会复活废弃作答或覆盖新评分依据。

队列 Redis 不可用时，可以依次运行只依赖 PostgreSQL 的补处理：

```bash
uv run python -m app.workers recover-attempts --limit 100
uv run python -m app.workers recover-grading --limit 100
```

检查输出的 `failed`，非零时排查后重试；未处理完则继续下一批或恢复常驻 worker。补交卷只能使用截止前服务器已保存的答案，不能补传离线答案。无可用阅卷教师的任务需要管理员改派，重跑 worker 不能替代授权操作。

## 管理员与会话恢复

管理员忘记密码时，在受保护的环境配置中更新 `ADMIN_PASSWORD`，核对 `ADMIN_LOGIN_NAME`，执行：

```bash
cd backend
uv run python -m app.cli reset-admin
```

命令会修改密码、递增认证版本并撤销旧会话；不要将密码作为命令参数。普通教师和学生由管理员人工核验后在页面重置为临时密码，下次登录强制改密。修改 `.env` 后需重启读取该配置的进程。

账号／密码修改已提交而 Redis 清理暂失败时，响应可能带 `X-Session-Cleanup: pending`。业务操作已经生效，不应重复提交；旧身份仍受数据库状态与认证版本限制。Redis 恢复后执行：

```bash
uv run python -m app.cli retry-session-cleanups --limit 100
```

查看 `attempted`、`completed`、`pending`、`failed`，必要时继续处理。刷新令牌轮换后响应丢失不能保证透明恢复，需要重新登录；不会重新计算考试截止时间。

## 常见问题

| 现象 | 检查与处理 |
|---|---|
| 登录后仍留在登录页／接口连不上 | 核对 API、Vite 代理和 Redis；确认前后使用同一主机名，生产 Cookie 与 HTTPS 配置一致 |
| 学生无法进入工作台 | 查看审核、停用状态和是否要求改密；待审核不是普通业务身份 |
| 到期后一直待处理 | 确认 worker 常驻、队列配置与 API 一致；查看补处理命令结果 |
| 阅卷任务等待指派 | 指定教师可能已停用或无可用教师，由管理员填写原因改派 |
| 已提交却没有成绩 | 检查考试是否结束、全部历史有效作答是否判完，以及是否公布／正在更正 |
| 成绩显示正常但不能回看 | 核对考试回看设置；禁止回看时只开放本人已公布总分 |
| 页面报告版本冲突 | 重新读取当前对象，核对他人的修改后再提交；不要盲目重复旧请求 |

## 正式环境边界

使用 HTTPS、Secure Cookie、独立随机密钥和受限的真实来源。数据库、Redis 和上传目录不要直接公开；图片通过 API 实时鉴权。生产静态服务需为前端路径配置 SPA 回退，并代理 `/api`，登录与写操作不能绕过 CSRF。

日志不记录请求密码、Cookie、连接凭据、学生答案或未公布参考答案。备份、凭据、数据库、图片与运行日志都不纳入 Git。负载测试的容量结论仅适用于其记录的硬件与工作负载，部署前应在目标环境复测。
