from app.core.errors import BusinessError


def audit_cursor(identifier):
    return f"a{identifier}"


def parse_audit_cursor(value):
    try:
        if not value.startswith("a") or not value[1:].isdigit():
            raise ValueError
        identifier = int(value[1:])
        if identifier > 2**63 - 1:
            raise ValueError
        return identifier
    except ValueError as exc:
        raise BusinessError("LOG_CURSOR_INVALID", "日志游标无效，请刷新后重试") from exc
