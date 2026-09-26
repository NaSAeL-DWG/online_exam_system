"""共享手工试卷；顺序唯一键延迟到事务提交检查。"""

from alembic import op
import sqlalchemy as sa

revision = "0005_papers"
down_revision = "0004_assets"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "paper",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("creator_id", sa.UUID(), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.Enum("ACTIVE", "ARCHIVED", name="paper_status"), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "paper_question",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("paper_id", sa.UUID(), sa.ForeignKey("paper.id"), nullable=False),
        sa.Column("question_id", sa.UUID(), sa.ForeignKey("question.id"), nullable=False),
        sa.Column("order_no", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(10, 1), nullable=False),
        sa.UniqueConstraint("paper_id", "question_id"),
        sa.UniqueConstraint("paper_id", "order_no", deferrable=True, initially="DEFERRED"),
        sa.CheckConstraint("order_no > 0"),
        sa.CheckConstraint("score > 0"),
    )


def downgrade():
    op.drop_table("paper_question")
    op.drop_table("paper")
    sa.Enum(name="paper_status").drop(op.get_bind())
