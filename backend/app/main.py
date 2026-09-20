from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import Resources
from .routes import admin, auth, classes, staff, student


def create_app() -> FastAPI:
    """创建配置隔离、可供集成测试启动的 FastAPI 应用。"""

    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.resources = Resources(settings)
        try:
            yield
        finally:
            await app.state.resources.close()

    app = FastAPI(title="在线限时考试系统 API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[value.strip() for value in settings.cors_origins.split(",") if value.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_, exc: RequestValidationError):
        fields = {".".join(str(p) for p in error["loc"]): error["msg"] for error in exc.errors()}
        return JSONResponse(
            status_code=422,
            content={"detail": {"code": "VALIDATION_ERROR", "message": "请求参数无效", "fields": fields}},
        )

    @app.get("/api/health")
    async def health():
        """返回 API 进程存活状态。"""

        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(student.router)
    app.include_router(staff.router)
    app.include_router(admin.router)
    app.include_router(classes.router)
    return app


app = create_app()
