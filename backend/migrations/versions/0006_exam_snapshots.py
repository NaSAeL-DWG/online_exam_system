"""创建考试时即持久化独立题目快照。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0006_exam_snapshots"
down_revision = "0005_papers"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.create_table(
        "exam",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("creator_id", sa.UUID(), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column("source_paper_id", sa.UUID(), sa.ForeignKey("paper.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "audience_type", sa.Enum("PUBLIC", "RESTRICTED", name="audience_type"), nullable=False
        ),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "RELEASED", "RESULTS_PUBLISHED", "CANCELLED", name="exam_status"),
            nullable=False,
        ),
        sa.Column("start_at", sa.DateTime(timezone=True)),
        sa.Column("end_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("allow_review", sa.Boolean(), nullable=False),
        sa.Column("shuffle_questions", sa.Boolean(), nullable=False),
        sa.Column("shuffle_options", sa.Boolean(), nullable=False),
        sa.Column(
            "multiple_choice_mode",
            sa.Enum("EXACT", "PARTIAL", name="multiple_choice_mode"),
            nullable=False,
        ),
        sa.Column("pass_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("total_score", sa.Numeric(10, 1), nullable=False),
        sa.Column("content_revision", sa.BigInteger(), nullable=False),
        sa.Column("grading_revision", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("warnings", pg.JSONB(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint("total_score >= 0"),
        sa.CheckConstraint("pass_percentage BETWEEN 0 AND 100"),
    )
    op.create_index("ix_exam_status_end", "exam", ["status", "end_at"])
    op.create_table(
        "exam_question",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("exam_id", sa.UUID(), sa.ForeignKey("exam.id"), nullable=False),
        sa.Column("source_question_id", sa.UUID(), sa.ForeignKey("question.id")),
        sa.Column(
            "source_paper_question_id",
            sa.UUID(),
            sa.ForeignKey("paper_question.id", ondelete="SET NULL"),
        ),
        sa.Column("order_no", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(10, 1), nullable=False),
        sa.Column(
            "type",
            pg.ENUM(
                "SINGLE_CHOICE",
                "MULTIPLE_CHOICE",
                "TRUE_FALSE",
                "SHORT_ANSWER",
                name="question_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("options", pg.JSONB(), nullable=False),
        sa.Column("standard_answer", pg.JSONB()),
        sa.Column("explanation", sa.Text()),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("knowledge_tags", pg.JSONB(), nullable=False),
        sa.Column(
            "difficulty",
            pg.ENUM("EASY", "MEDIUM", "HARD", name="question_difficulty", create_type=False),
            nullable=False,
        ),
        sa.Column("grading_revision", sa.BigInteger(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("exam_id", "source_question_id"),
        sa.UniqueConstraint("exam_id", "order_no", deferrable=True, initially="DEFERRED"),
        sa.CheckConstraint("order_no > 0"),
        sa.CheckConstraint("score > 0"),
    )


def downgrade():
    op.drop_table("exam_question")
    op.drop_table("exam")
    for name in ("multiple_choice_mode", "exam_status", "audience_type"):
        sa.Enum(name=name).drop(op.get_bind())
