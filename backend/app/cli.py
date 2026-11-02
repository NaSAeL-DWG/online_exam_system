import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime

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
    await resources.start_logging()
    try:
        async with resources.session_factory() as session:
            created = await initialize_admin(session, values)
        print("管理员已创建" if created else "管理员已存在")
        logging.getLogger(__name__).info("管理员初始化完成", extra={"task": "init_admin"})
    finally:
        await resources.close()


async def reset_admin(args):
    """本地运维复用版本递增、审计和持久补偿用例。"""
    settings = get_settings()
    login_name = args.login_name or settings.admin_login_name
    if not login_name or not settings.admin_password:
        raise RuntimeError("缺少 ADMIN_LOGIN_NAME 或 ADMIN_PASSWORD")
    resources = Resources(settings)
    await resources.start_logging()
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
        logging.getLogger(__name__).info("管理员重置完成", extra={"task": "reset_admin"})
    finally:
        await resources.close()


async def prepare_test_admin(args):
    """测试环境通过同一初始化业务能力准备固定身份。"""
    settings = get_settings()
    if settings.environment != "test":
        raise RuntimeError("prepare-test-admin 只能在测试环境运行")
    values = admin_values(settings, args)
    resources = Resources(settings)
    await resources.start_logging()
    try:
        async with resources.session_factory() as session:
            await initialize_admin(session, values, prepare_test=True)
        print("测试管理员已准备")
    finally:
        await resources.close()


async def retry_session_cleanups(args):
    """重试已提交的持久补偿并输出不含敏感信息的运行状态。"""
    resources = Resources(get_settings())
    await resources.start_logging()
    try:
        report = await retry_pending(resources.session_factory, resources.redis, args.limit)
        print(json.dumps(report))
        logging.getLogger(__name__).log(
            logging.INFO if any(report.values()) else logging.DEBUG,
            "会话清理补偿完成 %s",
            json.dumps(report),
            extra={"task": "retry_session_cleanups"},
        )
    finally:
        await resources.close()


async def logging_check(args):
    """通过标准 logging 验证跨进程采集；只发送固定诊断文本，不接受业务资料。"""
    settings = get_settings()
    timestamp = None
    if args.timestamp:
        if settings.environment != "test":
            raise RuntimeError("自定义日志时钟仅供测试环境验收")
        timestamp = datetime.fromisoformat(args.timestamp)
        if timestamp.tzinfo is None:
            raise RuntimeError("诊断时间须含时区")
    if not 1 <= args.count <= 100001 or not 1 <= args.message_size <= 4096:
        raise RuntimeError("count 范围为1..100001，message-size范围为1..4096")
    resources = Resources(settings)
    await resources.start_logging()
    collector = resources.log_collector
    try:
        for index in range(args.count):
            logging.getLogger("app.diagnostics").log(
                getattr(logging, args.level),
                "运行日志诊断 %s %s",
                index + 1,
                "x" * max(0, args.message_size - 32),
                extra={
                    "log_module": args.module,
                    "task": args.task,
                    "correlation_id": args.correlation_id,
                    "log_timestamp": timestamp,
                },
            )
            # 公开诊断入口主动让批量写入器前进；业务日志仍使用不阻塞的有界缓冲。
            if index % 1000 == 999:
                await collector.flush()
        await collector.flush()
        print(json.dumps({"emitted": args.count, "dropped": collector.dropped}))
        if collector.dropped:
            raise RuntimeError("诊断记录未能全部持久化")
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
    diagnostic = commands.add_parser("logging-check", help="通过标准logging发送固定安全诊断记录")
    diagnostic.add_argument(
        "--level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO"
    )
    diagnostic.add_argument("--module", default="cli")
    diagnostic.add_argument("--task", default="diagnostic")
    diagnostic.add_argument("--correlation-id")
    diagnostic.add_argument("--count", type=positive_limit, default=1)
    diagnostic.add_argument("--message-size", type=positive_limit, default=64)
    diagnostic.add_argument("--timestamp")
    diagnostic.set_defaults(handler=logging_check)
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
