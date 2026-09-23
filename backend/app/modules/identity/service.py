from contextlib import asynccontextmanager

from sqlalchemy.exc import IntegrityError

from app.core.contracts import Page
from app.core.errors import BusinessError
from app.modules.auth.password import hash_password, verify_password
from . import crud
from .models import (
    RegistrationReview,
    ReviewStatus,
    StudentProfile,
    TeacherProfile,
    User,
    UserStatus,
    UserType,
    utc_now,
)
from .schemas import (
    ApplicationPublic,
    ApplicationResponse,
    RegistrationResponse,
    ReviewPublic,
    UserPublic,
    UserResponse,
    UserSummary,
)
from .types import Credentials


@asynccontextmanager
async def identity_transaction(session):
    """顶层用例持有事务，仅翻译明确的账号唯一约束。"""
    try:
        async with session.begin():
            yield
    except IntegrityError as exc:
        cause = getattr(exc.orig, "__cause__", None)
        constraint = getattr(cause, "constraint_name", None)
        if constraint in {
            "user_account_login_name_key",
            "student_profile_student_no_key",
            "teacher_profile_teacher_no_key",
        }:
            raise BusinessError("LOGIN_NAME_EXISTS", "登录账号已存在") from None
        raise


def ensure_role(user, *allowed, active=True):
    if user.status == UserStatus.DEACTIVATED:
        raise BusinessError("ACCOUNT_DEACTIVATED", "账号已停用")
    if active and user.must_change_password:
        raise BusinessError("PASSWORD_CHANGE_REQUIRED", "请先修改临时密码")
    if active and user.status != UserStatus.ACTIVATED:
        raise BusinessError("ACCOUNT_NOT_ACTIVE", "账号尚未激活")
    if allowed and user.user_type not in allowed:
        raise BusinessError("FORBIDDEN", "没有执行此操作的权限")


async def locked_actor(session, identity, *roles, active=True):
    """重读并锁定身份；快照不能替代实时权限和版本检查。"""
    user = await crud.user_by_id(session, identity.user.id, lock=True)
    if user is None or user.auth_version != identity.auth_version:
        raise BusinessError("SESSION_INVALID", "登录已失效")
    ensure_role(user, *roles, active=active)
    return user


async def validate_actor(session, identity, *roles, active=True):
    """跨模块公开能力，在调用方事务内锁定并验证身份。"""
    return UserPublic.model_validate(await locked_actor(session, identity, *roles, active=active))


async def credentials_by_login(session, login_name, *, lock=False):
    user = await crud.user_by_login(session, login_name, lock=lock)
    return (
        Credentials(UserPublic.model_validate(user), user.password_hash, user.auth_version)
        if user
        else None
    )


async def credentials_by_id(session, user_id, *, lock=False):
    user = await crud.user_by_id(session, user_id, lock=lock)
    return (
        Credentials(UserPublic.model_validate(user), user.password_hash, user.auth_version)
        if user
        else None
    )


async def summaries(session, user_ids):
    return {
        user.id: UserSummary.model_validate(user)
        for user in await crud.users_by_ids(session, user_ids)
    }


def record_audit(session, **values):
    """组合审计与调用方业务数据同事务持久化。"""
    crud.add_audit(session, **values)


def profile_snapshot(payload):
    return {
        "student_no": payload.student_no,
        "real_name": payload.real_name,
        "email": str(payload.email),
        "phone_number": payload.phone_number,
    }


async def register_student(session, payload):
    password_hash = await hash_password(payload.password)
    async with identity_transaction(session):
        user = User(
            login_name=payload.student_no,
            password_hash=password_hash,
            phone_number=payload.phone_number,
            email=str(payload.email),
            real_name=payload.real_name,
            user_type=UserType.STUDENT,
            status=UserStatus.WAITING_ACTIVATE,
        )
        await crud.add_user(
            session, user, StudentProfile(user_id=user.id, student_no=payload.student_no)
        )
        application = RegistrationReview(
            user_id=user.id, submitted_profile=profile_snapshot(payload)
        )
        crud.add_review(session, application)
        record_audit(
            session,
            actor_id=user.id,
            action="REGISTRATION_SUBMITTED",
            entity_type="registration_review",
            entity_id=application.id,
            after_data={"student_no": payload.student_no},
        )
        result = RegistrationResponse(
            user=UserPublic.model_validate(user),
            application=ApplicationPublic.model_validate(application),
        )
    return result


async def get_application(session, identity):
    ensure_role(identity.user, UserType.STUDENT, active=False)
    application = await crud.latest_review(session, identity.user.id)
    if application is None:
        raise BusinessError("APPLICATION_NOT_FOUND", "未找到注册申请")
    return ApplicationResponse(application=ApplicationPublic.model_validate(application))


async def resubmit_application(session, identity, payload):
    async with identity_transaction(session):
        user = await locked_actor(session, identity, UserType.STUDENT, active=False)
        if user.must_change_password:
            raise BusinessError("PASSWORD_CHANGE_REQUIRED", "请先修改临时密码")
        latest = await crud.latest_review(session, user.id)
        if latest is None or latest.status != ReviewStatus.REJECTED:
            raise BusinessError("APPLICATION_NOT_REJECTED", "仅被拒绝的申请可以重新提交")
        profile = await crud.profile_for_user(session, user)
        user.login_name = payload.student_no
        user.real_name = payload.real_name
        user.email = str(payload.email)
        user.phone_number = payload.phone_number
        user.updated_at = utc_now()
        profile.student_no = payload.student_no
        profile.updated_at = utc_now()
        application = RegistrationReview(
            user_id=user.id, submitted_profile=profile_snapshot(payload)
        )
        crud.add_review(session, application)
        record_audit(
            session,
            actor_id=user.id,
            action="REGISTRATION_RESUBMITTED",
            entity_type="registration_review",
            entity_id=application.id,
            after_data={"student_no": payload.student_no},
        )
        result = ApplicationResponse(application=ApplicationPublic.model_validate(application))
    return result


async def decide_review(session, identity, review_id, payload):
    async with identity_transaction(session):
        await locked_actor(session, identity, UserType.ADMIN, UserType.TEACHER)
        review = await crud.review_by_id(session, review_id, lock=True)
        if review is None:
            raise BusinessError("REVIEW_NOT_FOUND", "审核申请不存在")
        if review.status != ReviewStatus.PENDING:
            raise BusinessError("REVIEW_ALREADY_DECIDED", "审核申请已处理")
        user = await crud.user_by_id(session, review.user_id, lock=True)
        review.status = ReviewStatus(payload.decision)
        review.reason = payload.reason.strip() if payload.reason else None
        review.reviewer_id = identity.user.id
        review.reviewed_at = utc_now()
        if review.status == ReviewStatus.APPROVED and user.status != UserStatus.DEACTIVATED:
            user.status = UserStatus.ACTIVATED
        record_audit(
            session,
            actor_id=identity.user.id,
            action="REGISTRATION_REVIEW_DECIDED",
            entity_type="registration_review",
            entity_id=review.id,
            reason=review.reason,
            after_data={"status": review.status.value},
        )
        result = ApplicationResponse(application=ApplicationPublic.model_validate(review))
    return result


async def create_teacher(session, identity, payload):
    password_hash = await hash_password(payload.temporary_password)
    async with identity_transaction(session):
        await locked_actor(session, identity, UserType.ADMIN)
        user = User(
            login_name=payload.teacher_no,
            password_hash=password_hash,
            real_name=payload.real_name,
            email=str(payload.email),
            phone_number=payload.phone_number,
            user_type=UserType.TEACHER,
            status=UserStatus.ACTIVATED,
            must_change_password=True,
        )
        await crud.add_user(
            session, user, TeacherProfile(user_id=user.id, teacher_no=payload.teacher_no)
        )
        record_audit(
            session,
            actor_id=identity.user.id,
            action="TEACHER_CREATED",
            entity_type="user",
            entity_id=user.id,
            after_data={"teacher_no": payload.teacher_no},
        )
        result = UserResponse(user=UserPublic.model_validate(user))
    return result


async def list_users(session, identity, pagination, user_type=None, status=None):
    ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    if identity.user.user_type == UserType.TEACHER and user_type != UserType.STUDENT:
        raise BusinessError("FORBIDDEN", "教师仅可查询学生")
    rows, total = await crud.list_users(session, pagination, user_type, status)
    return Page[UserPublic](
        items=[UserPublic.model_validate(user) for user in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def list_reviews(session, identity, pagination, status=None):
    ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    rows, total = await crud.list_reviews(session, pagination, status)
    items = [
        ReviewPublic(
            **ApplicationPublic.model_validate(review).model_dump(),
            user=UserSummary.model_validate(user),
        )
        for review, user in rows
    ]
    return Page[ReviewPublic](
        items=items, total=total, page=pagination.page, page_size=pagination.page_size
    )


async def patch_user(session, identity, user_id, payload):
    from app.modules.auth.cleanup import schedule

    async with identity_transaction(session):
        await locked_actor(session, identity, UserType.ADMIN)
        user = await crud.user_by_id(session, user_id, lock=True)
        if user is None:
            raise BusinessError("USER_NOT_FOUND", "用户不存在")
        requested_status = UserStatus(payload.status) if payload.status else None
        if user.user_type == UserType.ADMIN and requested_status == UserStatus.DEACTIVATED:
            raise BusinessError("ADMIN_DEACTIVATION_FORBIDDEN", "管理员账号不能通过后台停用")
        before = {
            "login_name": user.login_name,
            "real_name": user.real_name,
            "status": user.status.value,
        }
        if payload.login_name is not None and payload.login_name != user.login_name:
            profile = await crud.profile_for_user(session, user)
            user.login_name = payload.login_name
            if isinstance(profile, StudentProfile):
                profile.student_no = payload.login_name
            elif isinstance(profile, TeacherProfile):
                profile.teacher_no = payload.login_name
        if payload.real_name is not None:
            user.real_name = payload.real_name
        task = None
        if requested_status is not None and requested_status != user.status:
            restored_status = requested_status
            if requested_status == UserStatus.ACTIVATED and user.user_type == UserType.STUDENT:
                latest = await crud.latest_review(session, user.id)
                if latest is None or latest.status != ReviewStatus.APPROVED:
                    if user.status != UserStatus.DEACTIVATED:
                        raise BusinessError("REVIEW_REQUIRED", "学生尚未通过审核")
                    restored_status = UserStatus.WAITING_ACTIVATE
            user.status = restored_status
            user.auth_version += 1
            task = schedule(session, user.id, revoke_before_version=user.auth_version)
        user.updated_at = utc_now()
        record_audit(
            session,
            actor_id=identity.user.id,
            action="USER_UPDATED",
            entity_type="user",
            entity_id=user.id,
            before_data=before,
            after_data={
                "login_name": user.login_name,
                "real_name": user.real_name,
                "status": user.status.value,
            },
        )
        result = UserResponse(user=UserPublic.model_validate(user))
    return result, task.id if task else None


async def replace_password(session, identity, current_password, new_hash):
    """可组合写操作：锁刷新后验证旧密码与身份版本，调用方持事务。"""
    user = await locked_actor(session, identity, active=False)
    if not await verify_password(user.password_hash, current_password):
        raise BusinessError("CURRENT_PASSWORD_INVALID", "当前密码错误")
    user.password_hash = new_hash
    user.must_change_password = False
    user.auth_version += 1
    user.updated_at = utc_now()
    record_audit(
        session, actor_id=user.id, action="PASSWORD_CHANGED", entity_type="user", entity_id=user.id
    )
    return user.auth_version


async def replace_contacts(session, identity, payload):
    user = await locked_actor(session, identity, active=False)
    if user.must_change_password:
        raise BusinessError("PASSWORD_CHANGE_REQUIRED", "请先修改临时密码")
    if not await verify_password(user.password_hash, payload.current_password):
        raise BusinessError("CURRENT_PASSWORD_INVALID", "当前密码错误")
    before = {"email": user.email, "phone_number": user.phone_number}
    user.email = str(payload.email)
    user.phone_number = payload.phone_number
    user.updated_at = utc_now()
    record_audit(
        session,
        actor_id=user.id,
        action="CONTACTS_CHANGED",
        entity_type="user",
        entity_id=user.id,
        before_data=before,
        after_data={"email": user.email, "phone_number": user.phone_number},
    )
    return UserResponse(user=UserPublic.model_validate(user))


async def reset_password(session, user_id, new_hash, *, identity=None, cli=False):
    """可组合重置：HTTP 与本地运维共用密码版本及审计规则。"""
    if not cli:
        await locked_actor(session, identity, UserType.ADMIN)
    user = await crud.user_by_id(session, user_id, lock=True)
    if user is None:
        raise BusinessError("USER_NOT_FOUND", "用户不存在")
    if user.user_type == UserType.ADMIN and not cli:
        raise BusinessError("ADMIN_RESET_REQUIRES_CLI", "管理员密码必须通过本地运维命令重置")
    user.password_hash = new_hash
    user.must_change_password = not cli
    user.auth_version += 1
    user.updated_at = utc_now()
    record_audit(
        session,
        actor_id=identity.user.id if identity else None,
        action="ADMIN_PASSWORD_RESET_CLI" if cli else "PASSWORD_RESET",
        entity_type="user",
        entity_id=user.id,
    )
    return user.auth_version


async def initialize_admin(session, values, *, prepare_test=False):
    password_hash = await hash_password(values["password"])
    async with identity_transaction(session):
        existing = await crud.admin(session)
        if existing and not prepare_test:
            if existing.login_name != values["login_name"]:
                raise BusinessError("ADMIN_EXISTS", "已存在其他管理员账号")
            return False
        if existing:
            existing = await crud.user_by_id(session, existing.id, lock=True)
            existing.login_name = values["login_name"]
            existing.password_hash = password_hash
            existing.real_name = values["real_name"]
            existing.email = values["email"]
            existing.phone_number = values["phone_number"]
            existing.status = UserStatus.ACTIVATED
            existing.auth_version += 1
            existing.updated_at = utc_now()
        else:
            user = User(
                login_name=values["login_name"],
                password_hash=password_hash,
                real_name=values["real_name"],
                email=values["email"],
                phone_number=values["phone_number"],
                user_type=UserType.ADMIN,
                status=UserStatus.ACTIVATED,
            )
            await crud.add_user(session, user)
    return True
