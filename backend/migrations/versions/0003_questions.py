"""共享题库及不可变题目内容基础。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_questions"
down_revision = "0002_session_cleanup"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "question",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("creator_id", sa.UUID(), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "SINGLE_CHOICE",
                "MULTIPLE_CHOICE",
                "TRUE_FALSE",
                "SHORT_ANSWER",
                name="question_type",
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("standard_answer", postgresql.JSONB()),
        sa.Column("explanation", sa.Text()),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("knowledge_tags", postgresql.JSONB(), nullable=False),
        sa.Column(
            "difficulty",
            sa.Enum("EASY", "MEDIUM", "HARD", name="question_difficulty"),
            nullable=False,
        ),
        sa.Column("status", sa.Enum("ACTIVE", "CLOSED", name="question_status"), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_question_subject", "question", ["subject"])


def downgrade():
    op.drop_table("question")
    for name in ("question_status", "question_difficulty", "question_type"):
        sa.Enum(name=name).drop(op.get_bind())
