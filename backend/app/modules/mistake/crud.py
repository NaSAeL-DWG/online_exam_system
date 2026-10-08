from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.core.clock import utc_now
from .models import MistakeAnnotation


async def annotations(session, user_id, answer_ids):
    return (
        await session.scalars(
            select(MistakeAnnotation).where(
                MistakeAnnotation.user_id == user_id, MistakeAnnotation.answer_id.in_(answer_ids)
            )
        )
    ).all()


async def mastered_ids(session, user_id):
    return list(
        await session.scalars(
            select(MistakeAnnotation.answer_id).where(
                MistakeAnnotation.user_id == user_id, MistakeAnnotation.mastered.is_(True)
            )
        )
    )


async def save_annotation(session, user_id, answer_id, note, mastered):
    now = utc_now()
    statement = insert(MistakeAnnotation).values(
        user_id=user_id,
        answer_id=answer_id,
        note=note,
        mastered=mastered,
        created_at=now,
        updated_at=now,
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=["user_id", "answer_id"],
            set_={"note": note, "mastered": mastered, "updated_at": now},
        )
    )
