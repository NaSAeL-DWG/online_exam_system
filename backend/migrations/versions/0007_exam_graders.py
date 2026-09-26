"""指定阅卷教师。"""

from alembic import op
import sqlalchemy as sa

revision = "0007_exam_graders"
down_revision = "0006_exam_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "exam_grader",
        sa.Column("exam_id", sa.UUID(), sa.ForeignKey("exam.id"), primary_key=True),
        sa.Column("teacher_id", sa.UUID(), sa.ForeignKey("user_account.id"), primary_key=True),
        sa.Column("assigned_by", sa.UUID(), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("exam_grader")
