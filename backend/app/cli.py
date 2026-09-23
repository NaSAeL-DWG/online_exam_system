import argparse
import asyncio
import json
import sys

from .config import get_settings
from .db import Resources
from .core.errors import BusinessError
from .modules.auth.cleanup import retry_pending
from .modules.auth.service import reset_admin as reset_admin_use_case
from .modules.identity.service import initialize_admin


def admin_values(settings, args):
    values = {
        "login_name": getattr(args, "login_name", None) or settings.admin_login_name,
        "password": settings.admin_password,
        "real_name": getattr(args, "real_name", None) or settings.admin_real_name,
        "email": getattr(args, "email", None) or settings.admin_email,
        "phone_number": getattr(args, "phone_number", None) or settings.admin_phone_number,
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"缺少管理员配置：{', '.join(missing)}")
    return values


async def init_admin(args):
    """通过身份用例幂等初始化管理员。"""
    settings = get_settings()
    values = admin_values(settings, args)
    resources = Resources(settings)
    try:
        async with resources.session_factory() as session:
            created = await initialize_admin(session, values)
        print("管理员已创建" if created else "管理员已存在")
    finally:
        await resources.close()


async def reset_admin(args):
    """本地运维复用版本递增、审计和持久补偿用例。"""
    settings = get_settings()
    login_name = args.login_name or settings.admin_login_name
    if not login_name or not settings.admin_password:
        raise RuntimeError("缺少 ADMIN_LOGIN_NAME 或 ADMIN_PASSWORD")
    resources = Resources(settings)
    try:
        async with resources.session_factory() as session:
            complete = await reset_admin_use_case(
                session,
                resources.session_factory,
                resources.redis,
                login_name,
                settings.admin_password,
            )
        print("管理员密码已重置" + ("" if complete else "；会话清理待补偿"))
    finally:
        await resources.close()


async def prepare_test_admin(args):
    """测试环境通过同一初始化业务能力准备固定身份。"""
    settings = get_settings()
    if settings.environment != "test":
        raise RuntimeError("prepare-test-admin 只能在测试环境运行")
    values = admin_values(settings, args)
    resources = Resources(settings)
    try:
        async with resources.session_factory() as session:
            await initialize_admin(session, values, prepare_test=True)
        print("测试管理员已准备")
    finally:
        await resources.close()


async def retry_session_cleanups(args):
    """重试已提交的持久补偿并输出不含敏感信息的运行状态。"""
    resources = Resources(get_settings())
    try:
        report = await retry_pending(resources.session_factory, resources.redis, args.limit)
        print(json.dumps(report))
    finally:
        await resources.close()


def positive_limit(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("limit 必须为正整数")
    return number


def build_parser():
    parser = argparse.ArgumentParser(description="在线考试系统管理员运维命令")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init-admin")
    for name in ("login-name", "real-name", "email", "phone-number"):
        init.add_argument(f"--{name}")
    init.set_defaults(handler=init_admin)
    reset = commands.add_parser("reset-admin")
    reset.add_argument("--login-name")
    reset.set_defaults(handler=reset_admin)
    commands.add_parser("prepare-test-admin").set_defaults(handler=prepare_test_admin)
    retry = commands.add_parser("retry-session-cleanups")
    retry.add_argument("--limit", type=positive_limit, default=100)
    retry.set_defaults(handler=retry_session_cleanups)
    return parser


def main():
    args = build_parser().parse_args()
    try:
        asyncio.run(args.handler(args))
    except BusinessError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
