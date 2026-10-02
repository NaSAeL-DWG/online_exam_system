"""限时作答提交、页面写权限、逐题答案及持久展示顺序。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0009_attempt_runtime"
down_revision = "0008_participants_attempts"
branch_labels = None
depends_on = None


def upgrade():
    submission = sa.Enum("MANUAL", "TIMEOUT", name="submission_type")
    grading = sa.Enum("PENDING", "GRADING", "GRADED", name="grading_status")
    submission.create(op.get_bind())
    grading.create(op.get_bind())
    for name in ("last_active_at", "submitted_at", "effective_submitted_at"):
        op.add_column("exam_attempt", sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column("exam_attempt", sa.Column("submission_type", submission))
    op.add_column(
        "exam_attempt",
        sa.Column("grading_status", grading, nullable=False, server_default="PENDING"),
    )
    op.add_column(
        "exam_attempt",
        sa.Column("grading_revision", sa.BigInteger(), nullable=False, server_default="1"),
    )
    op.add_column("exam_attempt", sa.Column("active_token_hash", sa.String(64)))
    op.add_column(
        "exam_attempt",
        sa.Column("active_token_generation", sa.BigInteger(), nullable=False, server_default="0"),
    )
    for name in ("grading_status", "grading_revision", "active_token_generation"):
        op.alter_column("exam_attempt", name, server_default=None)
    op.create_table(
        "stu_answer",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("attempt_id", sa.UUID(), sa.ForeignKey("exam_attempt.id"), nullable=False),
        sa.Column("exam_question_id", sa.UUID(), sa.ForeignKey("exam_question.id"), nullable=False),
        sa.Column("answer_data", postgresql.JSONB()),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("attempt_id", "exam_question_id"),
    )
    op.create_table(
        "attempt_question_order",
        sa.Column("attempt_id", sa.UUID(), sa.ForeignKey("exam_attempt.id"), primary_key=True),
        sa.Column(
            "exam_question_id", sa.UUID(), sa.ForeignKey("exam_question.id"), primary_key=True
        ),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("option_order", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("attempt_id", "display_order"),
        sa.CheckConstraint("display_order > 0"),
    )


def downgrade():
    op.drop_table("attempt_question_order")
    op.drop_table("stu_answer")
    for name in (
        "active_token_generation",
        "active_token_hash",
        "grading_revision",
        "grading_status",
        "submission_type",
        "effective_submitted_at",
        "submitted_at",
        "last_active_at",
    ):
        op.drop_column("exam_attempt", name)
    sa.Enum(name="grading_status").drop(op.get_bind())
    sa.Enum(name="submission_type").drop(op.get_bind())
