# 并发验证与复现

2026-10-09 在下述本地环境完成三轮各 100 名学生的真实 HTTP 作答验证。每名学生具有独立账号、Cookie 会话、作答和页面令牌；每份 20 道客观题。结果只代表该环境和短时工作负载，不是生产容量或长期稳定性保证。

## 环境与数据

| 项目 | 实测配置 |
|---|---|
| 系统／CPU／内存 | Windows 11、Intel i7-14650HX、24 逻辑核、约 15.61 GiB |
| 运行时 | Python 3.13.14、FastAPI 0.117.1、Uvicorn 0.36.0 |
| 存储 | PostgreSQL 18.3、Redis 8.8 |
| 进程 | 一个 API 应用进程、一个独立 ARQ worker；另有空闲开发服务 |
| 数据库连接 | 各进程 SQLAlchemy 基础池 5、溢出 10；PostgreSQL max_connections=100 |
| 隔离目标 | `exam_test_iteration6_load`、Redis DB 13、API 18001、每轮独立队列 |
| 最终数据量 | 417 账号、12 考试、416 作答、8064 答案，数据库约 18.46 MiB |

每轮新增 100 份作答和 2000 条答案。准备账号与登录单独计时，不计入下表的考试业务请求；每次最多 5 个并发登录，不关闭认证限流。另用同 IP、同一不存在账号发送 12 次登录请求，每轮均为 10 个 401 与 2 个 429。

## 结果

学生执行考试列表／详情读取、开始、激活、逐题保存与重新读取；手动交卷轮次还提交并核对收据。50 人使用全对语料、50 人全错，独立核对最后答案、提交状态和 50／0 分的对应关系。

| 场景 | 业务请求 | 业务阶段 | p50／p95／p99 | 后续一致性 |
|---|---:|---:|---|---|
| 5 秒错峰，每题 0.75—1.25 秒思考，worker 常驻 | 4600／4600 成功 | 45.147 秒 | 318.189／763.738／1024.583 ms | 100 人提交、答案、判分一致 |
| 同步开始、零思考，worker 暂停后恢复 | 4600／4600 成功 | 33.123 秒 | 687.415／1222.081／1548.858 ms | 恢复前 100 提交／0 已判，恢复后 100 全判且一致 |
| 零思考保存，真实 60 秒截止后启动 worker | 4400／4400 成功 | 31.594 秒 | 692.297／1242.856／1567.858 ms | 100 份 TIMEOUT 自动提交且全判，有效提交时间均等于 deadline |

三轮均没有 5xx 或传输错误，峰值最大在途请求为 100。稳态整体 p95 小于 1 秒，但开始／激活接口的 p95 分别为 1033.194／1015.225 ms，不能把整体百分位解读为每个接口都低于 1 秒。

峰值手动交卷轮的恢复观察窗口为 6.530 秒，包含启动前工作人员 HTTP 核对、worker 启动和最终核对；它不是纯 worker 执行耗时。真实截止轮从启动 worker 到确认全部补提交、判分的观察窗口为 5.552 秒。

稳态 API 进程树 RSS 峰值约 131.56 MiB，worker 约 92.05 MiB；API CPU 峰值 106.513% 是单核口径。整机 CPU 峰值 61.69%，最低可用物理内存约 383 MiB，桌面背景进程和内存压力显著。工具按实际 Windows 子解释器进程树采样；曾误测启动器的初版数据已排除，不计入以上资源结果。

## 复现

先安装锁定后端依赖，启动本机 PostgreSQL 与 Redis。私有 `.local/backend-test.env` 至少提供 `TEST_DATABASE_URL` 与 `TEST_REDIS_URL`，工具据此派生专用目标；来源数据库账号需有创建隔离库及迁移权限。先阅读[测试边界](testing.md)。

```bash
cd backend
uv run python scripts/verify_concurrency.py --source-env ../.local/backend-test.env --check-only
uv run python scripts/verify_concurrency.py --source-env ../.local/backend-test.env \
  --students 100 --questions 20 --mode steady --worker-policy running
uv run python scripts/verify_concurrency.py --source-env ../.local/backend-test.env \
  --students 100 --questions 20 --mode peak --worker-policy recover
uv run python scripts/verify_concurrency.py --source-env ../.local/backend-test.env \
  --students 100 --questions 20 --mode peak --worker-policy recover \
  --submission timeout --deadline-seconds 60
```

串行执行，不同时运行其他负载或浏览器测试。工具只接受本机地址、固定隔离库和 18001 端口；不会清空开发库，也不停止已经占用端口的未知服务。它自行启动／停止专用 API 与 worker，保留数据；输出位于忽略的 `.local/iteration6/load/`，含私有运行配置，不整体提交。

保留每轮 `summary.json`、请求时延和资源采样，报告中百分位采用最近秩。再次运行会积累数据，应记录新的起止规模。Linux 支持 `/proc` 资源采样，本轮正式结论来自 Windows。

## 适用范围

本轮覆盖短时本机 HTTP 在线作答、保存、提交和后台恢复，不包含 100 人同瞬间登录、广域网延迟、长时间在线、图片大文件、简答人工阅卷负载或大量历史数据。部署环境的硬件、网络和题目规模不同，应重新执行符合实际使用节奏的容量验证。
