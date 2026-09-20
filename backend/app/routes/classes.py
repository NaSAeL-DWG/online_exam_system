from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Identity, get_session, require_csrf, roles
from ..errors import api_error
from ..models import (
    AuditEvent,
    ClassMember,
    ClassStatus,
    MemberRole,
    TeachingClass,
    User,
    UserStatus,
    UserType,
    utc_now,
)
from ..schemas import (
    ClassCreateRequest,
    ClassPatchRequest,
    ClassPublic,
    MemberPutRequest,
    UserSummary,
)

router = APIRouter(prefix="/api/classes", tags=["教学班"])
staff_identity = roles(UserType.TEACHER, UserType.ADMIN)
admin_identity = roles(UserType.ADMIN)


async def _can_manage(session: AsyncSession, identity: Identity, class_id: UUID) -> bool:
    if identity.user.user_type == UserType.ADMIN:
        return True
    member = await session.get(ClassMember, (class_id, identity.user.id))
    return bool(member and member.role == MemberRole.TEACHER)


async def _class_public(
    session: AsyncSession, item: TeachingClass, include_students: bool
) -> ClassPublic:
    rows = (
        await session.execute(
            select(ClassMember, User)
            .join(User, User.id == ClassMember.user_id)
            .where(ClassMember.class_id == item.id)
            .order_by(User.real_name)
        )
    ).all()
    teachers = [
        UserSummary.model_validate(user)
        for member, user in rows
        if member.role == MemberRole.TEACHER
    ]
    students = [
        UserSummary.model_validate(user)
        for member, user in rows
        if member.role == MemberRole.STUDENT
    ]
    return ClassPublic(
        id=item.id,
        name=item.name,
        description=item.description,
        status=item.status,
        teachers=teachers,
        students=students if include_students else None,
        student_count=len(students),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def _replace_teachers(session: AsyncSession, class_id: UUID, teacher_ids: list[UUID]):
    unique_ids = set(teacher_ids)
    if unique_ids:
        users = (
            await session.scalars(
                select(User).where(
                    User.id.in_(unique_ids),
                    User.user_type == UserType.TEACHER,
                    User.status == UserStatus.ACTIVATED,
                )
            )
        ).all()
        if len(users) != len(unique_ids):
            raise api_error(400, "INVALID_TEACHER", "教师必须存在且处于激活状态")
    await session.execute(
        delete(ClassMember).where(
            ClassMember.class_id == class_id, ClassMember.role == MemberRole.TEACHER
        )
    )
    session.add_all(
        [
            ClassMember(class_id=class_id, user_id=teacher_id, role=MemberRole.TEACHER)
            for teacher_id in unique_ids
        ]
    )


async def _teacher_ids(session: AsyncSession, class_id: UUID) -> list[str]:
    values = await session.scalars(
        select(ClassMember.user_id).where(
            ClassMember.class_id == class_id, ClassMember.role == MemberRole.TEACHER
        )
    )
    return [str(value) for value in values.all()]


@router.get("")
async def list_classes(
    identity: Identity = Depends(staff_identity), session: AsyncSession = Depends(get_session)
):
    """管理员查看全部班级，教师查看自己关联的班级。"""

    statement = select(TeachingClass)
    if identity.user.user_type == UserType.TEACHER:
        statement = statement.join(ClassMember).where(
            ClassMember.user_id == identity.user.id, ClassMember.role == MemberRole.TEACHER
        )
    classes = (await session.scalars(statement.order_by(TeachingClass.created_at.desc()))).all()
    items = [await _class_public(session, item, False) for item in classes]
    return {"items": items, "total": len(items)}


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
async def create_class(
    payload: ClassCreateRequest,
    identity: Identity = Depends(admin_identity),
    session: AsyncSession = Depends(get_session),
):
    """管理员创建教学班并关联负责教师。"""

    item = TeachingClass(
        name=payload.name, description=payload.description, creator_id=identity.user.id
    )
    session.add(item)
    await session.flush()
    await _replace_teachers(session, item.id, payload.teacher_ids)
    session.add(
        AuditEvent(
            actor_id=identity.user.id,
            action="CLASS_CREATED",
            entity_type="teaching_class",
            entity_id=item.id,
            after_data={"name": item.name, "teacher_ids": [str(v) for v in payload.teacher_ids]},
        )
    )
    await session.commit()
    await session.refresh(item)
    return {"class_info": await _class_public(session, item, True)}


@router.get("/{class_id}")
async def get_class(
    class_id: UUID,
    identity: Identity = Depends(staff_identity),
    session: AsyncSession = Depends(get_session),
):
    """查询有权维护的班级详情和成员。"""

    item = await session.get(TeachingClass, class_id)
    if not item:
        raise api_error(404, "CLASS_NOT_FOUND", "教学班不存在")
    if not await _can_manage(session, identity, class_id):
        raise api_error(403, "FORBIDDEN", "仅关联教师可查看此教学班")
    return {"class_info": await _class_public(session, item, True)}


@router.patch("/{class_id}", dependencies=[Depends(require_csrf)])
async def patch_class(
    class_id: UUID,
    payload: ClassPatchRequest,
    identity: Identity = Depends(admin_identity),
    session: AsyncSession = Depends(get_session),
):
    """管理员修改班级资料、负责教师或归档状态。"""

    item = await session.get(TeachingClass, class_id, with_for_update=True)
    if not item:
        raise api_error(404, "CLASS_NOT_FOUND", "教学班不存在")
    if payload.teacher_ids is not None and (
        item.status == ClassStatus.ARCHIVED or payload.status == ClassStatus.ARCHIVED
    ):
        raise api_error(409, "CLASS_ARCHIVED", "归档班级不能维护成员")
    previous_teacher_ids = await _teacher_ids(session, item.id)
    if payload.name is not None:
        item.name = payload.name
    if "description" in payload.model_fields_set:
        item.description = payload.description
    if payload.status is not None:
        item.status = payload.status
    if payload.teacher_ids is not None:
        await _replace_teachers(session, item.id, payload.teacher_ids)
    item.updated_at = utc_now()
    session.add(
        AuditEvent(
            actor_id=identity.user.id,
            action="CLASS_UPDATED",
            entity_type="teaching_class",
            entity_id=item.id,
            before_data={"teacher_ids": previous_teacher_ids},
            after_data={
                "name": item.name,
                "status": item.status.value,
                "teacher_ids": await _teacher_ids(session, item.id),
            },
        )
    )
    await session.commit()
    await session.refresh(item)
    return {"class_info": await _class_public(session, item, True)}


@router.put("/{class_id}/members/{user_id}", dependencies=[Depends(require_csrf)])
async def put_member(
    class_id: UUID,
    user_id: UUID,
    payload: MemberPutRequest,
    identity: Identity = Depends(staff_identity),
    session: AsyncSession = Depends(get_session),
):
    """管理员维护全部成员，关联教师维护激活学生成员。"""

    item = await session.get(TeachingClass, class_id, with_for_update=True)
    if not item:
        raise api_error(404, "CLASS_NOT_FOUND", "教学班不存在")
    if item.status == ClassStatus.ARCHIVED:
        raise api_error(409, "CLASS_ARCHIVED", "归档班级不能维护成员")
    if not await _can_manage(session, identity, class_id):
        raise api_error(403, "FORBIDDEN", "仅关联教师可维护此教学班")
    if identity.user.user_type == UserType.TEACHER and payload.role != MemberRole.STUDENT:
        raise api_error(403, "FORBIDDEN", "教师只能维护学生成员")
    user = await session.get(User, user_id)
    expected_type = UserType(payload.role.value)
    if not user or user.user_type != expected_type or user.status != UserStatus.ACTIVATED:
        raise api_error(400, "INVALID_MEMBER", "成员必须角色匹配且处于激活状态")
    existing = await session.get(ClassMember, (class_id, user_id))
    if existing:
        existing.role = payload.role
    else:
        session.add(ClassMember(class_id=class_id, user_id=user_id, role=payload.role))
    session.add(
        AuditEvent(
            actor_id=identity.user.id,
            action="CLASS_MEMBER_ADDED",
            entity_type="teaching_class",
            entity_id=item.id,
            after_data={"user_id": str(user_id), "role": payload.role.value},
        )
    )
    await session.commit()
    return {"class_info": await _class_public(session, item, True)}


@router.delete(
    "/{class_id}/members/{user_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def delete_member(
    class_id: UUID,
    user_id: UUID,
    identity: Identity = Depends(staff_identity),
    session: AsyncSession = Depends(get_session),
):
    """从教学班移出成员并保留审计记录。"""

    item = await session.get(TeachingClass, class_id, with_for_update=True)
    if not item:
        raise api_error(404, "CLASS_NOT_FOUND", "教学班不存在")
    if item.status == ClassStatus.ARCHIVED:
        raise api_error(409, "CLASS_ARCHIVED", "归档班级不能维护成员")
    if not await _can_manage(session, identity, class_id):
        raise api_error(403, "FORBIDDEN", "仅关联教师可维护此教学班")
    member = await session.get(ClassMember, (class_id, user_id))
    if not member:
        raise api_error(404, "MEMBER_NOT_FOUND", "班级成员不存在")
    if identity.user.user_type == UserType.TEACHER and member.role != MemberRole.STUDENT:
        raise api_error(403, "FORBIDDEN", "教师只能维护学生成员")
    await session.delete(member)
    session.add(
        AuditEvent(
            actor_id=identity.user.id,
            action="CLASS_MEMBER_REMOVED",
            entity_type="teaching_class",
            entity_id=item.id,
            before_data={"user_id": str(user_id), "role": member.role.value},
        )
    )
    await session.commit()
