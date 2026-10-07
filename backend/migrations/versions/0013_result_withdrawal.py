"""更正评分前撤回既有结果的时间与原因。"""

from alembic import op
import sqlalchemy as sa

revision = "0013_result_withdrawal"
down_revision = "0012_grading_history_order"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("exam", sa.Column("results_published_at", sa.DateTime(timezone=True)))
    op.add_column("exam", sa.Column("results_withdrawn_at", sa.DateTime(timezone=True)))
    op.add_column("exam", sa.Column("results_withdraw_reason", sa.Text()))


def downgrade():
    for name in ("results_withdraw_reason", "results_withdrawn_at", "results_published_at"):
        op.drop_column("exam", name)
