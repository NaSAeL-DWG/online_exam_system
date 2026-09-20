import argparse
import asyncio

from sqlalchemy import select

from .config import get_settings
from .db import Resources
from .models import AuditEvent, User, UserStatus, UserType, utc_now
from .security import hash_password, revoke_all_sessions


async def init_admin(args: argparse.Namespace) -> None:
    """幂等创建唯一的初始管理员账号。"""

    settings = get_settings()
    values = {
        "login_name": args.login_name or settings.admin_login_name,
        "password": settings.admin_password,
        "real_name": args.real_name or settings.admin_real_name,
        "email": args.email or settings.admin_email,
        "phone_number": args.phone_number or settings.admin_phone_number,
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(f"缺少管理员配置：{', '.join(missing)}")
    resources = Resources(settings)
    try:
        async with resources.session_factory() as session:
            existing_admin = await session.scalar(
                select(User).where(User.user_type == UserType.ADMIN)
            )
            if existing_admin:
                if existing_admin.login_name == values["login_name"]:
                    print(f"管理员已存在：{existing_admin.login_name}")
                    return
                raise RuntimeError("已存在其他管理员账号")
            if await session.scalar(select(User).where(User.login_name == values["login_name"])):
                raise RuntimeError("登录账号已存在")
            admin = User(
                login_name=values["login_name"],
                password_hash=await hash_password(values["password"]),
                real_name=values["real_name"],
                email=values["email"],
                phone_number=values["phone_number"],
                user_type=UserType.ADMIN,
                status=UserStatus.ACTIVATED,
            )
            session.add(admin)
            await session.commit()
            print(f"管理员已创建：{admin.login_name}")
    finally:
        await resources.close()


async def reset_admin(args: argparse.Namespace) -> None:
    """本地运维重置管理员密码并撤销旧会话。"""

    settings = get_settings()
    login_name = args.login_name or settings.admin_login_name
    if not login_name or not settings.admin_password:
        raise RuntimeError("缺少 ADMIN_LOGIN_NAME 或 ADMIN_PASSWORD")
    resources = Resources(settings)
    try:
        async with resources.session_factory() as session:
            admin = await session.scalar(
                select(User).where(User.user_type == UserType.ADMIN, User.login_name == login_name)
            )
            if not admin:
                raise RuntimeError("管理员账号不存在")
            admin.password_hash = await hash_password(settings.admin_password)
            admin.auth_version += 1
            admin.updated_at = utc_now()
            session.add(
                AuditEvent(
                    actor_id=None,
                    action="ADMIN_PASSWORD_RESET_CLI",
                    entity_type="user",
                    entity_id=admin.id,
                )
            )
            await session.commit()
            await revoke_all_sessions(resources.redis, admin.id)
            print(f"管理员密码已重置：{admin.login_name}")
    finally:
        await resources.close()


async def prepare_test_admin(_: argparse.Namespace) -> None:
    """仅在测试环境中创建或统一测试管理员凭据。"""

    settings = get_settings()
    if settings.environment != "test":
        raise RuntimeError("prepare-test-admin 只能在测试环境运行")
    required = (
        settings.admin_login_name,
        settings.admin_password,
        settings.admin_real_name,
        settings.admin_email,
        settings.admin_phone_number,
    )
    if not all(required):
        raise RuntimeError("测试管理员配置不完整")
    resources = Resources(settings)
    try:
        async with resources.session_factory() as session:
            admin = await session.scalar(select(User).where(User.user_type == UserType.ADMIN))
            if admin is None:
                admin = User(
                    login_name=settings.admin_login_name,
                    password_hash=await hash_password(settings.admin_password),
                    real_name=settings.admin_real_name,
                    email=settings.admin_email,
                    phone_number=settings.admin_phone_number,
                    user_type=UserType.ADMIN,
                    status=UserStatus.ACTIVATED,
                )
                session.add(admin)
            else:
                admin.login_name = settings.admin_login_name
                admin.password_hash = await hash_password(settings.admin_password)
                admin.real_name = settings.admin_real_name
                admin.email = settings.admin_email
                admin.phone_number = settings.admin_phone_number
                admin.status = UserStatus.ACTIVATED
                admin.auth_version += 1
                admin.updated_at = utc_now()
            await session.commit()
            await revoke_all_sessions(resources.redis, admin.id)
            print("测试管理员已准备")
    finally:
        await resources.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="在线考试系统管理员运维命令")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init-admin")
    init.add_argument("--login-name")
    init.add_argument("--real-name")
    init.add_argument("--email")
    init.add_argument("--phone-number")
    init.set_defaults(handler=init_admin)
    reset = subparsers.add_parser("reset-admin")
    reset.add_argument("--login-name")
    reset.set_defaults(handler=reset_admin)
    prepare = subparsers.add_parser("prepare-test-admin")
    prepare.set_defaults(handler=prepare_test_admin)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(args.handler(args))


if __name__ == "__main__":
    main()
