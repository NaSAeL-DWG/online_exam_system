# 后端工程与维护指南 (`backend/`)

**中文** | [English](README.en.md)

本目录包含 **在线限时考试系统** 的 FastAPI 后端服务、ARQ 异步 Worker、CLI 运维工具、Alembic 数据库迁移及 HTTP 集成测试。

> **全局文档索引**：首次配置环境变量与启动步骤请看 **[快速启动指南 (`../docs/quick-start.md`)](../docs/quick-start.md)**；全局架构规范请看 **[架构设计与开发规范 (`../docs/development.md`)](../docs/development.md)**。

---

## 一、目录结构与模块划分

后端采用 **按业务领域切分的三层模块化单体架构**，所有业务模块位于 `app/modules/` 下：

```text
backend/
├── app/
│   ├── core/                 # 全局基础设施（配置、数据库连接、时钟、错误码、统一中文校验转换、运行日志缓冲）
│   ├── modules/              # 12 个独立业务模块（每个模块内含 router / service / crud / models / schemas）
│   │   ├── auth/             # 登录、HttpOnly Cookie 签发、单次 Refresh Token 轮换、CSRF、会话清理补偿
│   │   ├── identity/         # 管理员/教师/学生账号、学生注册审核、密码重置、操作审计记录
│   │   ├── teaching_class/   # 教学班管理、多教师关联、班级学生成员维护
│   │   ├── asset/            # 题目图片上传、本地持久化存储与实时鉴权读取
│   │   ├── question/         # 共享题库（单选/多选/判断/简答）、分类筛选、关闭归档
│   │   ├── paper/            # 共享试卷编排、题序调整、小数分值汇总
│   │   ├── exam/             # 考试创建、独立考试快照深拷贝、考生资格名单、发布/撤回/取消、结果公布
│   │   ├── attempt/          # 学生限时作答、固定截止时间、单页面写租约（Page Lease）、逐题保存、交卷
│   │   ├── grading/          # 客观题自动判分、整卷人工阅卷任务均分、首阅与留痕改分、标准答案更正重判
│   │   ├── results/          # 学生成绩历史、最终成绩计算（取最后一次有效提交）、受保护快照回看
│   │   ├── mistake/          # 错题自动归集、多维筛选、个人复习笔记与“已掌握”标记
│   │   ├── analytics/        # 教师端考试统计分布、学生端个人得分率趋势与知识点掌握分析
│   │   └── logging/          # 管理员运行日志查询、累加等级过滤、15 分钟临时 DEBUG 采集、文件轮转导出
│   ├── workers/              # ARQ 异步任务与纯 PostgreSQL 故障恢复命令（attempts / grading / recovery）
│   ├── demo/                 # 通过公开 HTTP 接口生成可重复演示数据的工具（python -m app.demo）
│   ├── cli.py                # 运维 CLI（init-admin / reset-admin / retry-session-cleanups / logging-check）
│   └── main.py               # FastAPI 应用入口与中间件挂载
├── migrations/               # Alembic 数据库版本迁移（0001 ~ 0018）
├── scripts/                  # 100 人并发压测脚本（verify_concurrency.py）与启动脚本测试
└── tests/                    # 基于真实 PostgreSQL / Redis 的 HTTP 集成测试套件
```

### 核心分层铁律
1. **三层边界（`router → service → crud`）**：
   - `router` 只管请求参数、依赖注入、CSRF 和 Cookie，不直接查 ORM、不提交事务。
   - `service` 掌管资源权限校验、状态流转、操作审计和 **顶层数据库事务（一个写用例一次 `commit`）**，下级被调用的函数严禁私自提前 `commit`。
   - `crud` 只管 SQLAlchemy/SQLModel 查询、行锁（`with_for_update`）、分页与 `flush`，不做业务权限判断。
2. **读写会话与行锁刷新**：
   - 鉴权依赖使用独立的只读 Session，返回包含公开资料与 `auth_version` 的不可变身份快照。
   - 写操作在独立的新事务 Session 中重新锁定并读取实体（配合 `populate_existing`），拿到数据库最新状态和版本号后再执行业务判断。
3. **统一分页与精度约定**：
   - 所有列表接口统一接收 `page`（默认 1）、`page_size`（默认 20，最大 100）和可选搜索词 `q`，返回 `{ items, total, page, page_size }`。
   - 拒绝 N+1 查询：例如教学班列表仅聚合学生人数并批量读取关联教师，进入班级详情时才按需读取学生名单。
   - 所有分值与比率在 JSON 中一律使用十进制字符串传输，后端内部一律使用 `Decimal` 计算。

---

## 二、核心技术机制说明

### 1. 认证安全、Refresh Token 单次轮换与会话清理补偿
- **Refresh Token 原子轮换（CAS）**：刷新令牌时先读取会话，再加锁校验数据库用户状态与 `auth_version`，最后通过 Redis Lua 脚本执行原子 CAS 替换。旧 Refresh Token 一旦被重放会立即吊销整条会话；若刷新途中数据库暂不可用返回 `503 DATABASE_UNAVAILABLE`（原令牌仍可重试），若 Redis 不可用则返回 `503 AUTH_SERVICE_UNAVAILABLE`（绝不降级放行）。
- **会话清理异步补偿（`0002_session_cleanup`）**：当修改密码、重置密码或停用账号在 PostgreSQL 事务中提交成功（`auth_version` 已递增并能立即拦截旧请求），但随后清理 Redis 旧会话时网络闪断，接口仍正常返回 `200`/`204` 并附带响应头 `X-Session-Cleanup: pending`（告知前端业务已生效，切勿重发写请求）。Redis 恢复后可通过 CLI 批量补偿清理：
  ```bash
  uv run python -m app.cli retry-session-cleanups --limit 100
  ```
  *(注：Lua 脚本仅清理版本号低于撤销时上界的旧会话，不会误删用户用新密码重新登录产生的新会话。)*

### 2. 限时作答、客观题判分与人工阅卷恢复
- **作答与写租约（`attempt`）**：服务端固定计算 `deadline_at`（取个人时长与考试结束时间较早值），通过 `page_token` 与 `active_token_generation` 代次保证同一份答卷同时只有一个活动页面拥有写权限，每次保存校验答案修订号。
- **判分与派单（`grading`）**：学生交卷后向 ARQ 队列投递带评分修订号的任务；等整场考试结束且所有有效答卷均完成交卷和客观题自动判分后，系统自动将含非空简答题的答卷按“整份答卷”均分给指定的激活阅卷教师。教师更正单道题的评分标准时，仅重判受影响题目，完好保留其他题目的得分与首阅完成事实。
- **队列故障纯数据库补偿**：如果 Redis 队列暂时不可用，已落库的答卷绝不丢失。常驻 Worker 每 30 秒扫描一次数据库待办；运维也可直接运行纯依赖 PostgreSQL 的手动补偿命令：
  ```bash
  # 常驻 Worker 启动命令
  uv run arq app.workers.attempts.WorkerSettings

  # Redis 队列故障时的手动补偿命令（仅依赖 PostgreSQL）
  uv run python -m app.workers recover-attempts --limit 100
  uv run python -m app.workers recover-grading --limit 100
  ```

### 3. 成绩公布、错题与学习分析
- **成绩公布与撤回（`exam/publication.py` & `results`）**：在考试行锁下确认全部有效答卷及人工阅卷任务完成后，才允许公布结果。最终成绩严格取每名学生 **最后一次有效提交** （若该次仍在批改中，最终成绩为空/待批改，绝不回退展示上一次的旧分数）。撤回结果、撤销资格、取消考试或关闭回看开关，都会同步拦截答卷详情、受保护题目图片与学习分析的读取。
- **错题与统计（`mistake` & `analytics`）**：已公布且允许回看的有效答卷中，未满分的题目自动进入错题本（个人笔记与掌握标记存储在独立的 `0015_mistake_annotations` 表中，不影响原答卷）。统计模块实时查询数据库，公开考试不虚构应考人数分母，无样本指标返回空值。

---

## 三、常用开发、迁移与测试命令

所有命令在 `backend/` 目录下运行（依赖由 `uv.lock` 锁定在 Python 3.13）：

```bash
# 1. 安装/同步锁定依赖
uv sync --locked --python 3.13

# 2. 数据库迁移与模型一致性检查
uv run alembic upgrade head
uv run alembic check

# 3. 初始化或重置系统管理员（读取 backend/.env 中的 ADMIN_* 配置）
uv run python -m app.cli init-admin
uv run python -m app.cli reset-admin

# 4. 启动本地开发 API 服务
uv run uvicorn app.main:app --host 127.0.0.1 --port 18000

# 5. 代码静态检查与格式化检查
uv run ruff check app tests migrations
uv run ruff format --check app tests migrations

# 6. 运行真实 PostgreSQL / Redis 集成测试（需先准备隔离的 ../.local/backend-test.env）
set -a
source ../.local/backend-test.env
set +a
uv run python -m pytest -q --tb=short
```

> **提示**：日常开发请根据你修改的模块按需选择 `tests/test_*_api.py` 运行，不必每次跑全量测试。`--tb=short` 可避免测试报错回溯时打印包含连接串的 fixture 局部变量。更多测试细节请参阅 **[测试与验证指南 (`../docs/testing.md`)](../docs/testing.md)**。
