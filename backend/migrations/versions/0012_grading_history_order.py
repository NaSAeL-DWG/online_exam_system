"""以答案评分版本稳定排列同一时刻产生的历史。"""

from alembic import op
import sqlalchemy as sa

revision = "0012_grading_history_order"
down_revision = "0011_grading"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "grading_history",
        sa.Column("answer_version", sa.BigInteger(), nullable=False, server_default="1"),
    )
    op.alter_column("grading_history", "answer_version", server_default=None)


def downgrade():
    op.drop_column("grading_history", "answer_version")
