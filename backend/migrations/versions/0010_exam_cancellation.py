"""整场取消保留发生时间与强制原因，已有作答同事务废弃。"""

from alembic import op
import sqlalchemy as sa

revision = "0010_exam_cancellation"
down_revision = "0009_attempt_runtime"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("exam", sa.Column("cancelled_at", sa.DateTime(timezone=True)))
    op.add_column("exam", sa.Column("cancelled_reason", sa.Text()))


def downgrade():
    op.drop_column("exam", "cancelled_reason")
    op.drop_column("exam", "cancelled_at")
