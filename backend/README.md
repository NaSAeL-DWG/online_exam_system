# 后端维护说明

业务模块位于 `app/modules/identity`、`auth`、`teaching_class`。HTTP 路由负责参数、依赖和 Cookie；顶层业务用例持有事务；CRUD 负责 ORM 读写、锁刷新、分页和聚合。`app/models.py` 仅注册 Alembic 元数据，`app/config.py`、`app/db.py` 保留已有基础设施导入兼容入口。被替换的旧文件归档在项目 `.deletedfiles/backend-round1/`。

身份依赖使用独立只读 Session，输出包含公开资料和认证版本的不可变快照。写用例用新 Session 事务重读身份，并在 `FOR UPDATE + populate_existing` 后检查状态、角色和版本。CLI 的前置读取明确 rollback，随后复用同一密码重置用例。下级组合操作不提交事务；业务数据、认证版本和审计一起提交。

列表统一接受 `page`（默认 1）、`page_size`（默认 20，最大 100）、`q`，返回 `items/total/page/page_size`。原角色、状态过滤保持不变。教学班列表只聚合学生人数，批量读取教师；详情才读取学生。带教师的 1 班与 4 班列表均为 6 次 SELECT（含认证身份读取），响应映射不执行查询。班级详情成员暂不分页。

## 会话清理补偿

迁移 `0002_session_cleanup` 增加持久任务，和改密、联系方式、账号状态或密码重置同事务提交。数据库提交后清理失败仍返回原 200/204 成功状态，响应头 `X-Session-Cleanup: pending` 表示待补偿，`complete` 表示清理完成。浏览器不应重放已经完成的写操作。允许的跨源请求可读取该响应头。

数据库 `auth_version` 持续拒绝旧会话，即使 Redis 旧行尚未清理。任务记录撤销版本上界，Redis Lua 仅删除版本低于该上界的会话；迟到重试不删除重置后新登录的会话。联系方式任务只清理密码验证计数。

在配置好对应环境后运行：

```bash
uv run alembic upgrade head
uv run python -m app.cli retry-session-cleanups --limit 100
```

该命令每次处理最多 100 个待完成任务，输出 `attempted/completed/pending/failed` JSON。部署维护程序应定期调用，并监测 pending/failed；本轮未加入进程内定时器或自动调度器。单次恢复后若 pending 大于零，继续执行直至清空。每次尝试记录 attempts、last_attempt_at、last_error（仅异常类型），成功记录 completed_at；重复执行不产生重复业务审计。Redis 暂时不可用时任务继续保留，命令仍输出待处理数量；不能只根据进程退出码判断是否全部恢复。任务保留用于运维观察，暂未增加自动清理历史任务的策略。

## 刷新与故障边界

刷新先读取会话，再锁定用户并校验状态和版本，构造响应及 Access Token，最后执行 Redis 原子 CAS。数据库检查失败返回 `503 DATABASE_UNAVAILABLE`，原刷新凭据可重试。与停用、重置的用户行锁形成明确先后关系，旧版本即使已取得 Access Token 也不能继续访问。Redis 故障返回 `503 AUTH_SERVICE_UNAVAILABLE`，认证失败关闭。

Refresh Token 单次使用：CAS 竞争仅一个请求成功，旧凭据重放会撤销该会话。若 CAS 成功后响应丢失，服务端不能判断浏览器是否拿到新 Cookie；旧凭据重试得到 `401 SESSION_INVALID`，用户需要重新登录。此策略不承诺无感网络恢复。客户端必须协调并发刷新。

## 验证

```bash
set -a
source ../.local/backend-test.env
set +a
uv run python -m pytest -q --tb=short
uv run ruff check app tests migrations
uv run ruff format --check app tests migrations
```

测试依赖真实 PostgreSQL/Redis；`--tb=short` 避免失败时展示包含连接配置的 fixture 局部变量。保留迭代 1 的 18 项 HTTP 验收；本轮另有响应白名单/OpenAPI、依赖方向、分页 SQL 数量、提交后故障和 CLI 重试、刷新数据库故障/重放/竞态、先认证再并发重置或停用的用例。各次真实红绿结果由项目 `docs/` 统一记录。
