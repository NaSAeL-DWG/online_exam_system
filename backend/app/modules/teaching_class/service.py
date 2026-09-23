from app.core.clock import utc_now
from app.core.contracts import Page
from app.core.errors import BusinessError
from app.modules.identity import service as identity_service
from app.modules.identity.types import UserStatus, UserType
from . import crud
from .models import ClassStatus, MemberRole, TeachingClass
from .schemas import ClassPublic, ClassResponse


def class_public(item, teachers, students, student_count):
    """纯响应映射：所有关联资料由调用方预先批量加载。"""
    return ClassPublic(
        id=item.id,
        name=item.name,
        description=item.description,
        status=item.status,
        teachers=sorted(teachers, key=lambda user: (user.real_name, str(user.id))),
        students=sorted(students, key=lambda user: (user.real_name, str(user.id)))
        if students is not None
        else None,
        student_count=student_count,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def ensure_manage(session, identity, class_id):
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    if identity.user.user_type == UserType.ADMIN:
        return
    member = await crud.member(session, class_id, identity.user.id)
    if member is None or member.role != MemberRole.TEACHER:
        raise BusinessError("FORBIDDEN", "仅关联教师可维护此教学班")


async def require_class(session, class_id, *, lock=False):
    item = await crud.by_id(session, class_id, lock=lock)
    if item is None:
        raise BusinessError("CLASS_NOT_FOUND", "教学班不存在")
    return item


async def detail(session, item):
    members = await crud.members(session, [item.id])
    summaries = await identity_service.summaries(session, {member.user_id for member in members})
    teachers = [
        summaries[member.user_id] for member in members if member.role == MemberRole.TEACHER
    ]
    students = [
        summaries[member.user_id] for member in members if member.role == MemberRole.STUDENT
    ]
    return ClassResponse(class_info=class_public(item, teachers, students, len(students)))


async def replace_teachers(session, class_id, teacher_ids):
    unique_ids = set(teacher_ids)
    users = await identity_service.summaries(session, unique_ids)
    if len(users) != len(unique_ids) or any(
        user.user_type != UserType.TEACHER or user.status != UserStatus.ACTIVATED
        for user in users.values()
    ):
        raise BusinessError("INVALID_TEACHER", "教师必须存在且处于激活状态")
    await crud.replace_teachers(session, class_id, unique_ids)


async def list_classes(session, identity, pagination):
    identity_service.ensure_role(identity.user, UserType.ADMIN, UserType.TEACHER)
    teacher_id = identity.user.id if identity.user.user_type == UserType.TEACHER else None
    rows, total = await crud.list_page(session, pagination, teacher_id)
    items = []
    if rows:
        class_ids = [item.id for item in rows]
        counts = await crud.student_counts(session, class_ids)
        members = await crud.members(session, class_ids, teachers_only=True)
        users = await identity_service.summaries(session, {member.user_id for member in members})
        teachers_by_class = {class_id: [] for class_id in class_ids}
        for member in members:
            teachers_by_class[member.class_id].append(users[member.user_id])
        items = [
            class_public(item, teachers_by_class[item.id], None, counts.get(item.id, 0))
            for item in rows
        ]
    return Page[ClassPublic](
        items=items, total=total, page=pagination.page, page_size=pagination.page_size
    )


async def get_class(session, identity, class_id):
    item = await require_class(session, class_id)
    await ensure_manage(session, identity, class_id)
    return await detail(session, item)


async def create_class(session, identity, payload):
    async with session.begin():
        await identity_service.validate_actor(session, identity, UserType.ADMIN)
        item = TeachingClass(
            name=payload.name, description=payload.description, creator_id=identity.user.id
        )
        await crud.add_class(session, item)
        await replace_teachers(session, item.id, payload.teacher_ids)
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="CLASS_CREATED",
            entity_type="teaching_class",
            entity_id=item.id,
            after_data={
                "name": item.name,
                "teacher_ids": [str(value) for value in payload.teacher_ids],
            },
        )
        result = await detail(session, item)
    return result


async def patch_class(session, identity, class_id, payload):
    async with session.begin():
        await identity_service.validate_actor(session, identity, UserType.ADMIN)
        item = await require_class(session, class_id, lock=True)
        if payload.teacher_ids is not None and (
            item.status == ClassStatus.ARCHIVED or payload.status == ClassStatus.ARCHIVED
        ):
            raise BusinessError("CLASS_ARCHIVED", "归档班级不能维护成员")
        previous = await crud.members(session, [class_id], teachers_only=True)
        if payload.name is not None:
            item.name = payload.name
        if "description" in payload.model_fields_set:
            item.description = payload.description
        if payload.status is not None:
            item.status = payload.status
        if payload.teacher_ids is not None:
            await replace_teachers(session, class_id, payload.teacher_ids)
        item.updated_at = utc_now()
        result = await detail(session, item)
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="CLASS_UPDATED",
            entity_type="teaching_class",
            entity_id=item.id,
            before_data={"teacher_ids": [str(member.user_id) for member in previous]},
            after_data={
                "name": item.name,
                "status": item.status.value,
                "teacher_ids": [str(user.id) for user in result.class_info.teachers],
            },
        )
    return result


async def membership_context(session, identity, class_id):
    await identity_service.validate_actor(session, identity, UserType.ADMIN, UserType.TEACHER)
    item = await require_class(session, class_id, lock=True)
    if item.status == ClassStatus.ARCHIVED:
        raise BusinessError("CLASS_ARCHIVED", "归档班级不能维护成员")
    await ensure_manage(session, identity, class_id)
    return item


async def put_member(session, identity, class_id, user_id, payload):
    async with session.begin():
        item = await membership_context(session, identity, class_id)
        if identity.user.user_type == UserType.TEACHER and payload.role != MemberRole.STUDENT:
            raise BusinessError("FORBIDDEN", "教师只能维护学生成员")
        users = await identity_service.summaries(session, [user_id])
        user = users.get(user_id)
        if (
            user is None
            or user.user_type.value != payload.role.value
            or user.status != UserStatus.ACTIVATED
        ):
            raise BusinessError("INVALID_MEMBER", "成员必须角色匹配且处于激活状态")
        await crud.put_member(session, class_id, user_id, payload.role)
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="CLASS_MEMBER_ADDED",
            entity_type="teaching_class",
            entity_id=item.id,
            after_data={"user_id": str(user_id), "role": payload.role.value},
        )
        result = await detail(session, item)
    return result


async def delete_member(session, identity, class_id, user_id):
    async with session.begin():
        item = await membership_context(session, identity, class_id)
        member = await crud.member(session, class_id, user_id)
        if member is None:
            raise BusinessError("MEMBER_NOT_FOUND", "班级成员不存在")
        if identity.user.user_type == UserType.TEACHER and member.role != MemberRole.STUDENT:
            raise BusinessError("FORBIDDEN", "教师只能维护学生成员")
        role = member.role
        await crud.remove_member(session, member)
        identity_service.record_audit(
            session,
            actor_id=identity.user.id,
            action="CLASS_MEMBER_REMOVED",
            entity_type="teaching_class",
            entity_id=item.id,
            before_data={"user_id": str(user_id), "role": role.value},
        )
