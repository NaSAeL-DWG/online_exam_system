"""单题评分、不可变历史及整份答卷人工任务。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

revision = "0011_grading"
down_revision = "0010_exam_cancellation"
branch_labels = None
depends_on = None


def upgrade():
    method = ENUM("AUTO", "MANUAL", name="grading_method")
    task_status = ENUM(
        "UNASSIGNED", "PENDING", "IN_PROGRESS", "COMPLETED", "VOID", name="grading_task_status"
    )
    method.create(op.get_bind())
    task_status.create(op.get_bind())
    existing_method = ENUM("AUTO", "MANUAL", name="grading_method", create_type=False)
    existing_task = ENUM(
        "UNASSIGNED",
        "PENDING",
        "IN_PROGRESS",
        "COMPLETED",
        "VOID",
        name="grading_task_status",
        create_type=False,
    )
    existing_grading = ENUM(
        "PENDING", "GRADING", "GRADED", name="grading_status", create_type=False
    )
    op.add_column("exam_attempt", sa.Column("final_score", sa.Numeric(10, 1)))
    op.add_column("exam_attempt", sa.Column("graded_at", sa.DateTime(timezone=True)))
    op.add_column(
        "stu_answer",
        sa.Column("grading_status", existing_grading, nullable=False, server_default="PENDING"),
    )
    op.add_column(
        "stu_answer",
        sa.Column("grading_revision", sa.BigInteger(), nullable=False, server_default="1"),
    )
    for name in ("grading_status", "grading_revision"):
        op.alter_column("stu_answer", name, server_default=None)
    op.add_column("stu_answer", sa.Column("score", sa.Numeric(10, 1)))
    op.add_column("stu_answer", sa.Column("is_correct", sa.Boolean()))
    op.add_column("stu_answer", sa.Column("grader_comment", sa.Text()))
    op.add_column("stu_answer", sa.Column("graded_by", sa.UUID(), sa.ForeignKey("user_account.id")))
    op.add_column("stu_answer", sa.Column("grading_method", existing_method))
    op.add_column("stu_answer", sa.Column("graded_at", sa.DateTime(timezone=True)))
    op.create_check_constraint("ck_answer_score_nonnegative", "stu_answer", "score >= 0")
    op.create_index("ix_answer_attempt_grading", "stu_answer", ["attempt_id", "grading_status"])
    op.create_table(
        "grading_task",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "attempt_id", sa.UUID(), sa.ForeignKey("exam_attempt.id"), nullable=False, unique=True
        ),
        sa.Column("assigned_teacher_id", sa.UUID(), sa.ForeignKey("user_account.id")),
        sa.Column("status", existing_task, nullable=False),
        sa.Column("grading_revision", sa.BigInteger(), nullable=False),
        sa.Column("first_review_completed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("assigned_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_task_teacher_status", "grading_task", ["assigned_teacher_id", "status"])
    op.create_table(
        "grading_history",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("answer_id", sa.UUID(), sa.ForeignKey("stu_answer.id"), nullable=False),
        sa.Column("grading_revision", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.UUID(), sa.ForeignKey("user_account.id")),
        sa.Column("method", existing_method, nullable=False),
        sa.Column("old_score", sa.Numeric(10, 1)),
        sa.Column("new_score", sa.Numeric(10, 1), nullable=False),
        sa.Column("old_is_correct", sa.Boolean()),
        sa.Column("new_is_correct", sa.Boolean(), nullable=False),
        sa.Column("old_comment", sa.Text()),
        sa.Column("new_comment", sa.Text()),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_grading_history_answer_created", "grading_history", ["answer_id", "created_at"]
    )


def downgrade():
    op.drop_table("grading_history")
    op.drop_table("grading_task")
    op.drop_index("ix_answer_attempt_grading", table_name="stu_answer")
    op.drop_constraint("ck_answer_score_nonnegative", "stu_answer", type_="check")
    for name in (
        "graded_at",
        "grading_method",
        "graded_by",
        "grader_comment",
        "is_correct",
        "score",
        "grading_revision",
        "grading_status",
    ):
        op.drop_column("stu_answer", name)
    op.drop_column("exam_attempt", "graded_at")
    op.drop_column("exam_attempt", "final_score")
    ENUM(name="grading_task_status").drop(op.get_bind())
    ENUM(name="grading_method").drop(op.get_bind())
