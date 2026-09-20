# 前端开发说明

前端使用 Vue 3、Vite、TypeScript、Naive UI、Vue Router、Pinia 和 Playwright。依赖版本已锁定在 `package-lock.json`。

## 本地启动

后端默认监听 `http://127.0.0.1:18000`，前端开发服务器会把 `/api` 代理到该地址。

```bash
npm ci
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`。如需修改后端地址，复制 `.env.example` 为 `.env.local` 并更改 `VITE_API_TARGET`。

## 检查与流程测试

```bash
npm run build
npm run format:check
set -a
source ../.local/e2e.env
set +a
npm run test:e2e
```

浏览器流程连接真实 API、PostgreSQL 和 Redis。管理员凭据通过 `E2E_ADMIN_LOGIN`、`E2E_ADMIN_PASSWORD` 注入，不能写入仓库。`E2E_BASE_URL` 可覆盖前端地址，未提供时 Playwright 会自行启动 5173 端口的开发服务器。
