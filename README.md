<div align="center">

# Online Exam System · 在线限时考试系统

**中文** | [English](README.en.md)

**面向教学机构的轻量、严谨、全流程在线限时考试平台**

[![GitHub Repo](https://img.shields.io/badge/GitHub-NaSAeL--DWG%2Fonline__exam__system-181717?logo=github)](https://github.com/NaSAeL-DWG/online_exam_system)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://github.com/NaSAeL-DWG/online_exam_system/blob/main/LICENSE)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.117-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3.5](https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![TypeScript 5.9](https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![PostgreSQL 18](https://img.shields.io/badge/PostgreSQL-18-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis 8](https://img.shields.io/badge/Redis-8-DC382D?logo=redis&logoColor=white)](https://redis.io/)

[快速上手](docs/quick-start.md) · [角色操作指南](docs/user-guide.md) · [文档中心](docs/README.md) · [架构与开发](docs/development.md) · [问题反馈](https://github.com/NaSAeL-DWG/online_exam_system/issues)

</div>

---

## 项目简介

**在线限时考试系统** （[NaSAeL-DWG/online_exam_system](https://github.com/NaSAeL-DWG/online_exam_system)）是一套专为单个教学机构打造的 Web 在线考试解决方案。系统围绕 **学生、教师、管理员** 三类角色构建，覆盖从日常备题、组卷、发布考试、限时作答、自动判分、人工批阅，到成绩公布、错题复盘与学习分析的完整教学闭环。

项目坚持 **“数据事实严谨、考试边界清晰、无 Docker 原生轻量运行”** 的工程理念：考试创建即生成独立快照，作答计时以服务端单调时钟为准，后台判分与超时收卷具备数据库级持久化兜底，确保考试过程公平、可靠、可追溯。

---

## 核心特性

- **三端角色协同，职责边界清晰**
  - **学生端**：自助注册申请、查看待考与进行中考试、专注模式限时作答、历次成绩查询、逐题答卷回看、错题笔记与掌握标记、个人学习趋势分析。
  - **教师端**：审核学生注册、管理所负责教学班、共建共享题库与试卷、发布公开或指定名单考试、批阅分配给自己的简答题、更正评分依据并重判、统一公布或撤回成绩。
  - **管理员端**：初始化与管理教师账号、创建教学班并指派教师、处理学生资格与密码重置、监控全站阅卷进度、改派异常阅卷任务、查看实时运行日志与安全审计。
- **独立考试快照，隔离题库变动**
  - 支持单选、多选、判断、简答四类题型，题干与解析支持 Markdown、LaTeX 数学公式（KaTeX）与受保护图片。
  - 从试卷创建考试时自动深拷贝生成 **独立考试快照（Exam Snapshot）**。后续修改题库原题或原试卷，绝不污染已创建或已开考的考试。
- **可靠的限时作答与单页面租约保护**
  - **服务端权威倒计时**：取“个人作答时长”与“整场考试截止时间”的较早值；断网、关网页或改电脑时间均不会暂停或延长计时。
  - **防多开覆盖（Page Lease）**：同一场作答同时只允许一个活动页面保存答案；换设备或新开标签页时支持一键安全接管，旧页面自动转为只读。
  - **异步收卷与容灾补偿**：ARQ 后台 Worker 负责超时自动收卷、客观题秒级判分与主观题均分派单；即便 Redis 队列短暂抖动，数据库定时扫描也会自动兜底补判。
- **严谨的阅卷与成绩口径**
  - **整卷首阅 + 留痕改分**：主观题按整份答卷均分给指定阅卷教师；首阅完成后，其他激活教师可在填写改分原因的前提下复核调整，全程保留不可篡改的评分历史。
  - **“最后一次有效提交”原则**：允许多次作答的考试，最终成绩严格取最后一次有效交卷（而非历史最高分）；若最后一次仍在批改中，最终成绩显示“待批改”，绝不用旧分数冒充。
  - **发布考试 ≠ 公布成绩**：所有有效答卷批改完毕后，由教师显式执行“公布结果”才向学生开放成绩；若发现标准答案有误，可先撤回结果、更正依据触发重判，无误后再重新公布。

---

## 技术栈

| 领域 | 技术选型 | 说明 |
| :--- | :--- | :--- |
| **前端** | Vue 3.5 + TypeScript 5.9 + Vite 8 | 组合式 API、强类型接口契约 |
| **UI 与可视化** | Naive UI + ECharts 6 + KaTeX + Markdown-it | C3 定制设计系统（浅灰画布 + 纯白面板）、按需 SVG 图表、公式渲染 |
| **状态与路由** | Pinia 4 + Vue Router 5 | 角色路由守卫、跨标签页 Web Locks 认证刷新协调 |
| **后端框架** | Python 3.13 + FastAPI + Uvicorn | 异步 HTTP API、自动 OpenAPI 契约、统一中文表单校验 |
| **数据与 ORM** | PostgreSQL 18 + SQLModel + Alembic | 严格事务边界、行级锁并发控制、18 个版本可追溯数据库迁移 |
| **会话与任务队列** | Redis 8 + ARQ + Argon2 + PyJWT | HttpOnly Cookie + CSRF 双重校验、Refresh Token 单次轮换、异步判分 Worker |
| **测试与质量** | Pytest + Playwright + Ruff + Prettier | 真实 PostgreSQL/Redis 集成测试、Chromium 端到端测试、100 人并发实测脚本 |

---

## 仓库目录结构

```text
online_exam_system/
├── backend/                  # FastAPI 后端工程（详见 backend/README.md）
│   ├── app/
│   │   ├── core/             # 配置、数据库连接、安全认证、统一中文校验错误
│   │   ├── modules/          # 12 个业务模块（auth/identity/teaching_class/question/paper/exam/attempt/grading/results/mistake/analytics/logging）
│   │   ├── workers/          # ARQ 异步 Worker（超时交卷、客观题判分、阅卷派单、故障恢复命令）
│   │   └── cli.py            # 运维 CLI（初始化/重置管理员、清理会话补偿、日志自检）
│   ├── migrations/           # Alembic 数据库迁移脚本（0001 ~ 0018）
│   ├── scripts/              # 100 人并发压测与启动脚本验证工具
│   └── tests/                # 基于真实 PostgreSQL/Redis 的 HTTP 集成测试
├── frontend/                 # Vue 3 前端工程（详见 frontend/README.md）
│   ├── src/
│   │   ├── api/              # 类型化 HTTP 客户端、CSRF 与并发刷新协调
│   │   ├── components/       # 共享 UI 组件（PageHeader、SurfacePanel、AppSelect、LoadingSkeleton 等）
│   │   ├── design/ & styles/ # C3 主题色阶 Token 与全局布局样式
│   │   ├── features/         # 按领域划分的复杂业务组件与组合式逻辑（作答租约、阅卷工作台、图表等）
│   │   └── views/            # 学生、教师、管理员及公共页面视图
│   └── tests/e2e/            # Playwright 真实浏览器端到端测试套件
├── docs/                     # 面向使用者、开发者与运维人员的正式文档中心（纳入 Git）
├── CONTEXT.md                # 核心业务领域术语词典（区分试卷、考试、快照、作答与最终成绩）
└── start-local.ps1           # Windows 本地一键启动脚本（自动拉起 PG/Redis/API/Worker/Vite 并做健康检查）
```

---

## 快速开始

本项目本地运行 **无需 Docker**，直接运行原生 PostgreSQL、Redis、后端 API、ARQ Worker 与前端开发服务器。

### 环境要求

- **Python**: `3.13.x`（包管理器使用 `uv`）
- **Node.js**: `24.x`（包管理器使用 `npm`）
- **PostgreSQL**: `18.x`（需创建独立业务数据库）
- **Redis**: `8.x`（Windows 下推荐直接使用 WSL 内的 Redis）

### 方式一：Windows 一键启动（已完成首次配置后推荐）

完成首次依赖安装、环境变量配置（`backend/.env`）与数据库迁移后，在仓库根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1
```

脚本会按顺序检查并启动 PostgreSQL、WSL Redis、后端 API、ARQ Worker 和前端 Vite，自动验证端口与接口连通性。启动成功后在浏览器打开 `http://127.0.0.1:5173` 即可使用。

### 方式二：分步手动启动（首次安装必读）

1. **克隆仓库**
   ```bash
   git clone https://github.com/NaSAeL-DWG/online_exam_system.git
   cd online_exam_system
   ```

2. **配置后端并初始化数据库与管理员**
   ```bash
   cd backend
   uv sync --locked --python 3.13
   test -f .env || cp .env.example .env
   # 编辑 backend/.env，填入真实的 DATABASE_URL、REDIS_URL、JWT_SECRET 及管理员初始账号密码
   uv run alembic upgrade head
   uv run python -m app.cli init-admin
   uv run uvicorn app.main:app --host 127.0.0.1 --port 18000
   ```

3. **启动后台判分与收卷 Worker** （新开终端）
   ```bash
   cd backend
   uv run arq app.workers.attempts.WorkerSettings
   ```

4. **启动前端开发服务器** （新开终端）
   ```bash
   cd frontend
   npm ci
   npm run dev
   ```

5. **访问系统**
   - 前端界面：`http://127.0.0.1:5173`（请全程固定使用 `127.0.0.1`，勿与 `localhost` 混用，以免 Cookie 失效）
   - 后端接口文档（Swagger UI）：`http://127.0.0.1:18000/docs`

> 详细的 `.env` 配置项说明、常见问题排查与生产构建注意事项，请参阅 **[快速启动指南](docs/quick-start.md)**。

---

## 文档导航

我们整理了一套 **专业、通俗、有条理** 的项目文档，建议从 **[文档中心总目录 (`docs/README.md`)](docs/README.md)** 开始阅读：

| 阅读场景 | 推荐文档 | 核心内容 |
| :--- | :--- | :--- |
| **我是第一次跑项目** | [快速启动 (`docs/quick-start.md`)](docs/quick-start.md) | 环境准备、`.env` 必填项、三个进程启动顺序、Windows 一键脚本 |
| **我想快速体验完整功能** | [演示数据生成 (`docs/demo.md`)](docs/demo.md) | 一条命令生成 3 教师 + 6 学生 + 多状态考试的真实可交互演示环境 |
| **我想了解各角色怎么用** | [角色操作指南 (`docs/user-guide.md`)](docs/user-guide.md) | 学生参考与复盘、教师出题组卷与阅卷公布、管理员账号与异常处理 |
| **我想理清核心业务概念** | [领域术语词典 (`CONTEXT.md`)](CONTEXT.md) | 5 分钟分清“题库题目、试卷、考试、考试快照、答卷、最终成绩” |
| **我要参与前后端开发** | [架构与开发 (`docs/development.md`)](docs/development.md) · [后端 (`backend/README.md`)](backend/README.md) · [前端 (`frontend/README.md`)](frontend/README.md) | 三层单体边界、事务与行锁规约、认证安全、前端状态与改动流程 |
| **我要跑测试或做验证** | [测试与验证 (`docs/testing.md`)](docs/testing.md) | 真实 PG/Redis 后端集成测试、Playwright 浏览器测试、命令速查 |
| **我要管服务器与看日志** | [运维指南 (`docs/operations.md`)](docs/operations.md) · [系统日志 (`docs/logging.md`)](docs/logging.md) | 数据库迁移与回滚、备份恢复、Worker 补偿命令、日志筛选与轮转 |
| **我想看性能与 UI 规范** | [并发验证 (`docs/performance.md`)](docs/performance.md) · [UI 设计规范 (`docs/ui-design.md`)](docs/ui-design.md) | 100 人同时在线作答压测报告、C3 配色体系与全站 30 页视觉标准 |

---

## 项目范围与安全说明

- **当前版本边界**：聚焦单教学机构的高可靠核心考试流，暂不包含多租户隔离、代码沙箱判题、随机抽题组卷、Excel 批量导入导出、摄像头监考以及真实短信/邮件验证码发送（密码重置采用管理员人工核验后发放临时密码）。
- **敏感数据隔离**：仓库绝不内置通用弱口令或真实环境密钥。运行配置（`.env`）、上传图片、本地数据库目录、日志文件与测试截图均存放在 Git 忽略目录（如 `.local/`）中。

---

## 开源许可

本项目基于 [GNU General Public License v3.0 (GPL-3.0)](LICENSE) 协议开源。
