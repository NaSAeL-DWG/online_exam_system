from typing import Any

from fastapi import HTTPException


def api_error(status_code: int, code: str, message: str, fields: dict[str, Any] | None = None):
    """创建稳定、可供前端判断的 API 错误。"""

    detail: dict[str, Any] = {"code": code, "message": message}
    if fields:
        detail["fields"] = fields
    return HTTPException(status_code=status_code, detail=detail)
