"""独立持久化错题备注和掌握标记，不复制快照或成绩。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0015_mistake_annotations"
down_revision = "0014_grading_assignment_marker"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mistake_annotation",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_account.id"),
            primary_key=True,
        ),
        sa.Column(
            "answer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stu_answer.id"),
            primary_key=True,
        ),
        sa.Column("mastered", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("mistake_annotation")
