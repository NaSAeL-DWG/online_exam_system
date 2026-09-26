from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .db import Resources
from .modules.teaching_class import router as classes
from .modules.auth import router as auth
from .modules.identity import router as identity
from .modules.question import router as question
from .modules.asset import router as asset
from .core.errors import BusinessError, STATUS_CODES
from .core.contracts import HealthResponse
from sqlalchemy.exc import OperationalError, InterfaceError


def create_app(settings_override: Settings | None = None) -> FastAPI:
    """创建配置隔离、可供集成测试启动的 FastAPI 应用。"""

    settings = settings_override or get_settings()

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
        allow_origins=[
            value.strip() for value in settings.cors_origins.split(",") if value.strip()
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Session-Cleanup"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_, exc: RequestValidationError):
        fields = {".".join(str(p) for p in error["loc"]): error["msg"] for error in exc.errors()}
        return JSONResponse(
            status_code=422,
            content={
                "detail": {"code": "VALIDATION_ERROR", "message": "请求参数无效", "fields": fields}
            },
        )

    @app.get("/api/health", response_model=HealthResponse)
    async def health():
        """返回 API 进程存活状态。"""

        return {"status": "ok"}

    @app.exception_handler(BusinessError)
    async def business_error_handler(_, exc: BusinessError):
        return JSONResponse(
            status_code=STATUS_CODES[exc.code],
            content={"detail": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(OperationalError)
    @app.exception_handler(InterfaceError)
    async def database_error_handler(_, exc):
        return JSONResponse(
            status_code=503,
            content={
                "detail": {"code": "DATABASE_UNAVAILABLE", "message": "数据服务暂时不可用，请重试"}
            },
        )

    app.include_router(auth.router)
    app.include_router(identity.router)
    app.include_router(classes.router)
    app.include_router(question.router)
    app.include_router(asset.router)
    return app


app = create_app()
