# 在线限时考试系统

Vue + FastAPI 的在线考试项目。当前开发范围为迭代 1：学生注册审核、三角色登录、教学班维护及账号安全。题库、考试、作答、评分和统计按后续迭代实施。

- [需求与实施计划](docs/README.md)
- [本地运行与运维](docs/本地运行.md)
- [迭代 1 验证记录](docs/迭代1验证记录.md)

## 工程目录

```text
backend/       FastAPI、SQLModel、Alembic、HTTP 集成测试
frontend/      Vue、TypeScript、Naive UI、Pinia、Playwright
docs/          需求、逻辑模型、实施进度和运行说明
```

本地直接运行 PostgreSQL、Redis、API 和前端，不依赖 Docker。使用 `backend/uv.lock` 与 `frontend/package-lock.json` 锁定依赖。运行凭据放在未跟踪的 `.env`，不得提交到仓库。
