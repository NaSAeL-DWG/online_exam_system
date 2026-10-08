# 在线限时考试系统

Vue + FastAPI 的在线考试项目。迭代 1—4 已完成身份、考试准备、限时作答、可靠提交和阅卷闭环。迭代 5 的结果公布、学生历史／回看、错题及统计 API 已实现；前端与最终验收仍在推进，2026-10-09 按用户要求暂停，下一次从本轮剩余工作继续。

`docs/` 是本地需求、计划与验证记录，不再由 Git 追踪；以下文档链接适用于保留该目录的本地工作区。

- [需求与实施计划](docs/README.md)
- [本地运行与运维](docs/本地运行.md)
- [迭代 1 验证记录](docs/迭代1验证记录.md)
- [迭代 2 实施与验证记录](docs/迭代2验证记录.md)
- [迭代 3 限时作答验证记录](docs/迭代3验证记录.md)
- [迭代 4 判分与阅卷验证记录](docs/迭代4验证记录.md)
- [迭代 5 阶段验证与续接记录](docs/迭代5验证记录.md)

## 工程目录

```text
backend/       FastAPI、SQLModel、Alembic、HTTP 集成测试
frontend/      Vue、TypeScript、Naive UI、Pinia、Playwright
docs/          本地需求、逻辑模型、实施进度和运行说明（不追踪）
```

本地直接运行 PostgreSQL、Redis、API、独立 ARQ worker 和前端，不依赖 Docker。使用 `backend/uv.lock` 与 `frontend/package-lock.json` 锁定依赖。运行凭据放在未跟踪的 `.env`，不得提交到仓库。
