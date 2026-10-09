"""把 Pydantic 稳定错误类型转换为中文字段原因，避免暴露原始输入。"""

from collections.abc import Iterable, Mapping
from typing import Any


def field_reason(error: Mapping[str, Any]) -> str:
    """只使用错误类型、已知字段身份和约束上下文，不返回 raw msg/input。"""

    kind = error["type"]
    context = error.get("ctx") or {}
    location = error.get("loc") or ()
    if location and location[-1] == "email" and kind == "value_error":
        return "请输入有效的邮箱地址"
    if kind == "missing":
        return "请填写此项"
    if kind == "string_too_short":
        return f"至少需要{context['min_length']}个字符"
    if kind == "string_too_long":
        return f"最多允许{context['max_length']}个字符"
    if kind in {"string_type", "string_unicode"}:
        return "请输入有效文本"
    if kind in {"int_type", "int_parsing", "int_from_float"}:
        return "请输入整数"
    if kind in {"float_type", "float_parsing", "decimal_type", "decimal_parsing", "finite_number"}:
        return "请输入有效数字"
    if kind == "decimal_max_places":
        return f"最多保留{context['decimal_places']}位小数"
    if kind == "decimal_max_digits":
        return f"数字最多允许{context['max_digits']}位"
    comparisons = {
        "greater_than": ("gt", "需大于"),
        "greater_than_equal": ("ge", "需大于或等于"),
        "less_than": ("lt", "需小于"),
        "less_than_equal": ("le", "需小于或等于"),
    }
    if kind in comparisons:
        bound, text = comparisons[kind]
        return f"{text}{context[bound]}"
    if kind in {"uuid_parsing", "uuid_type", "uuid_version"}:
        return "请选择有效对象"
    if kind in {"literal_error", "enum", "bool_type", "bool_parsing"}:
        return "请选择有效值"
    if kind in {"datetime_parsing", "datetime_type", "datetime_from_date_parsing"}:
        return "请输入有效日期时间"
    if kind == "timezone_aware":
        return "日期时间需包含时区"
    if kind in {"too_short", "too_long"}:
        bound = "min_length" if kind == "too_short" else "max_length"
        text = "至少需要" if kind == "too_short" else "最多允许"
        return f"{text}{context[bound]}项"
    if kind in {"list_type", "dict_type", "model_type", "model_attributes_type"}:
        return "内容格式不正确"
    if kind == "json_invalid":
        return "请求内容格式不正确"
    return "内容不符合要求，请检查后重试"


def validation_fields(errors: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """保留兼容的点分隔字段路径，供前端就近关联表单字段。"""

    fields = {}
    for error in errors:
        path = ".".join(str(part) for part in error["loc"])
        fields.setdefault(path, field_reason(error))
    return fields
