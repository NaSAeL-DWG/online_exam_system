# 在线限时考试系统

面向单个教学机构的在线考试项目，使用 Vue、TypeScript、Naive UI、FastAPI、SQLModel、PostgreSQL 与 Redis/ARQ。支持管理员、教师和学生三种角色，覆盖共享题库、组卷、考试快照、限时作答、自动判分、人工阅卷、成绩公布、错题与学习分析。

## 开始使用

1. 按[快速启动](docs/quick-start.md)配置 PostgreSQL、Redis 和环境变量，迁移数据库并初始化管理员。
2. 分别运行 API、ARQ worker 与前端三个进程。
3. 打开 `http://127.0.0.1:5173`，按照[角色操作指南](docs/user-guide.md)完成注册审核、考试与阅卷流程。

本地运行无需 Docker。后端使用 Python 3.13 和 uv，前端使用 Node.js 24 和 npm，依赖版本由锁文件确定。管理员与演示账号的密码由运行环境提供，仓库不提供通用登录密码。

Windows 完成首次配置后，可在项目根目录执行 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1`，一并启动本地依赖、后端、worker 与前端；详见[快速启动脚本说明](docs/quick-start.md#windows-快速启动)。

## 文档

- [文档索引](docs/README.md)：按使用者、开发者和运维任务查阅。
- [开发与架构](docs/development.md)：目录职责、事务、前端结构和接口约定。
- [测试与验证](docs/testing.md)：真实 PostgreSQL/Redis 集成测试及浏览器流程。
- [迁移、备份与故障恢复](docs/operations.md)：升级／回滚、独立进程和管理员运维。
- [可重复演示数据](docs/demo.md)与[并发验证](docs/performance.md)：完整演示流程、实测环境、结果及复现命令。
- [领域术语](CONTEXT.md)：区分试卷、考试、答卷和最终成绩。

## 工程目录

```text
backend/       FastAPI、SQLModel、Alembic、HTTP 集成测试
frontend/      Vue、TypeScript、Naive UI、Pinia、Playwright
docs/          面向使用者和开发者的项目文档（纳入 Git）
tech-docs/     本地需求、开发计划、迭代记录及审查报告（不追踪）
```

迭代 1—6 已完成业务闭环、可重复演示数据、交付文档、100 人短时并发验证及三角色 UI/UX 审核。表单提供中文就近校验、密码辅助条和未保存保护。并发结论仅适用于文档记录的环境和工作负载。

第一版不包含多租户、代码执行判题、随机抽题、批量导入导出、摄像头监考或短信／邮件验证码实际发送。运行凭据、上传文件、数据库与测试报告保存在忽略目录中，不提交到仓库。
