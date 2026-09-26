# 在线限时考试系统

Vue + FastAPI 的在线考试项目。已完成身份审核、三角色登录、教学班与账号安全，以及迭代 2 的共享题库、预设试卷、独立考试快照、发布和资格管理。学生作答、评分和统计按后续迭代实施。

- [需求与实施计划](docs/README.md)
- [本地运行与运维](docs/本地运行.md)
- [迭代 1 验证记录](docs/迭代1验证记录.md)
- [迭代 2 实施与验证记录](docs/迭代2验证记录.md)

## 工程目录

```text
backend/       FastAPI、SQLModel、Alembic、HTTP 集成测试
frontend/      Vue、TypeScript、Naive UI、Pinia、Playwright
docs/          需求、逻辑模型、实施进度和运行说明
```

本地直接运行 PostgreSQL、Redis、API 和前端，不依赖 Docker。使用 `backend/uv.lock` 与 `frontend/package-lock.json` 锁定依赖。运行凭据放在未跟踪的 `.env`，不得提交到仓库。
