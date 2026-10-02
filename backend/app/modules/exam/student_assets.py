import re
from uuid import UUID

from app.core.clock import utc_now
from app.modules.attempt import service as attempt_service

from . import asset_crud


async def can_read_asset(session, student_id: UUID, asset_id: UUID) -> bool:
    """可组合授权能力：仅本人进行中作答的快照题干和选项授予资源访问。"""
    participants = await asset_crud.locked_student_participants(session, student_id, utc_now())
    if not participants:
        return False
    active_ids = set(
        await attempt_service.active_participant_ids(session, [row.id for row in participants])
    )
    exam_ids = [row.exam_id for row in participants if row.id in active_ids]
    if not exam_ids:
        return False
    # 资源地址必须完整匹配，不能把另一个路径中的 UUID 前缀视为快照引用。
    reference = re.compile(rf"/api/assets/{asset_id}(?=$|[\s)\]\"'<>?#])", re.IGNORECASE)
    for content, options in await asset_crud.snapshot_display_content(session, exam_ids):
        if reference.search(content) or any(
            reference.search(option["content"]) for option in options
        ):
            return True
    return False
