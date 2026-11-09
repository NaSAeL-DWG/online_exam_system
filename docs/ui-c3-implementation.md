# C3 正式前端落地总览

> **更新日期**：2026-11-06 · **状态**：全站 Vue 前端 C3 主题改造、30 个页面布局对齐与 E2E 自动化验证已全部完成。

本文档说明如何将已获批准的 **[C3 配色方案 (`ui-color-c3.md`)](ui-color-c3.md)**（基准原型为 [`design/ui-redesign/color.html`](../design/ui-redesign/color.html)）落地到真实的 `frontend/` Vue 3 工程中，并列出核心组件约定与回归测试命令。

---

## 一、改造覆盖范围

| 模块领域 | 核心落地内容 | 状态 |
| :--- | :--- | :---: |
| **全局视觉基础** | 4 个十阶主色族 + 10 阶中性灰写入 CSS Token 与 Naive UI 主题；统一输入框内边框焦点、下拉浮层阴影与骨架屏白光横扫动画 | 已完成 |
| **全局导航与公共页** | `204 px` 纯白直角侧栏（`0 px` 圆角 + `3 px` 蓝色选中条）、`#F6F7F9` 浅灰工作区画布、左蓝右白登录页、`760 px` 居中注册卡片 | 已完成 |
| **学生端全链路** | 学生首页（当前考试只读倒计时卡 + 近期考试/学习记录双栏）、考试详情三卡、专注作答页、退出保存提醒、交卷收据、成绩/回看/错题/学习分析 | 已完成 |
| **教师端全链路** | 教师工作台（待阅任务优先 + 四格统计）、题库与试卷页级编辑工作区、考试配置主栏 + `300 px` 发布检查侧栏、专注答卷评分工作区 | 已完成 |
| **管理员职责收敛** | 移除管理员的一线阅卷工作台与直接打分入口；管理员专注账号、班级、审核、系统日志以及考试详情里的“阅卷进度监控与任务改派” | 已完成 |

---

## 二、前端开发与组件复用约定

后续在 `frontend/` 中新增或修改页面时，请严格遵守以下工程约定：

1. **主题变量唯一来源**
   - CSS 变量统一定义在 `src/styles/tokens.css`，Naive UI 组件主题映射定义在 `src/design/theme.ts`。
   - 写样式时一律引用语义 Token（如画布 `#F6F7F9`、主色 Blue 600 `#2164CE`），严禁硬编码旧版的绿色主题值。
2. **核心共享组件**
   - `PageHeader.vue`：统一提供英文眉题、30px 页面主标题与右侧主操作区。
   - `SurfacePanel.vue`：统一的纯白内容卡片容器。
   - `AppSelect.vue`：全站统一的下拉选择器，封装了带阴影的弹出列表、真实焦点的 `combobox` 语义、搜索多选与完整键盘方向键导航。
   - `LoadingSkeleton.vue`：支持 `list`、`table`、`detail` 三种骨架屏模式，内置 3.2 秒周期的白光横扫动画（自动响应操作系统的“减少动态效果”无障碍设置）。
3. **坚持真实数据边界，绝不造假**
   - **学生首页**：当前考试与接下来两场考试从近期列表中提取；个人倒计时与答题进度通过**只读作答快照接口**推算，绝不在首页偷偷调用 `activate` 消耗考试机会或抢占其他标签页的写租约。
   - **考前详情页**：由于考前接口不提前暴露试卷题目明细，第三张“试卷结构”卡片诚实展示真实满分，并提示“题量与题型进入作答后查看”，不编造假题量。
   - **安全退出与异常兜底**：点击“退出作答界面”前会先尝试同步保存，弹窗明确区分“服务器已保存答案”与“未同步本地草稿”；若遇登录会话过期，直接跳回登录页，不被退出确认弹窗死锁。

---

## 三、自动化验证与复现命令

C3 前端改造通过了 **10 个专项 E2E 测试文件（共 42 项测试断言）**、全角色真实后端业务回归、TypeScript 类型检查与 Vite 生产打包验证，并在 `1440px` 桌面端和 `390px` 移动端下完成了全部 30 个页面场景的截图目检。

### 1. 快速运行 C3 视觉与交互专项测试（无需启动后端）
如果你修改了前端样式或共享组件，可在 `frontend/` 下直接运行基于固定接口快照的 C3 专项回归：

```bash
cd frontend
npx playwright test \
  tests/e2e/c3-foundation.spec.ts \
  tests/e2e/c3-content.spec.ts \
  tests/e2e/c3-student.spec.ts \
  tests/e2e/c3-implementation.spec.ts \
  tests/e2e/c3-review-details.spec.ts \
  --workers=1 \
  --output=../.local/ui-c3-implementation/c3-results

npm run build
npm run format:check
```

### 2. 运行全站 30 页布局还原测试套件
```bash
cd frontend
npx playwright test \
  tests/e2e/student-home-design.spec.ts \
  tests/e2e/student-pages-design.spec.ts \
  tests/e2e/staff-exam-pages-design.spec.ts \
  tests/e2e/content-admin-pages-design.spec.ts \
  tests/e2e/public-pages-design.spec.ts \
  --workers=1 \
  --output=../.local/c3-final-pages
```

> **延伸阅读**：各页面与静态设计稿的具体差异对比及真实接口适配细节，请查阅 **[C3 全站逐页落实总表 (`ui-c3-page-rollout.md`)](ui-c3-page-rollout.md)** 及其下属的[学生端](ui-c3-pages-student.md)、[教师与管理员考试端](ui-c3-pages-staff-exams.md)、[内容与系统管理端](ui-c3-pages-content-admin.md)分册记录。
