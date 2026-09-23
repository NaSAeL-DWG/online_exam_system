"""持久化提交后会话清理补偿。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_session_cleanup"
down_revision = "0001_identity_classes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "session_cleanup",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_account.id"),
            nullable=False,
        ),
        sa.Column("revoke_before_version", sa.Integer(), nullable=True),
        sa.Column("clear_password_rate", sa.Boolean(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_session_cleanup_pending", "session_cleanup", ["completed_at", "created_at"])


def downgrade():
    op.drop_index("ix_session_cleanup_pending", table_name="session_cleanup")
    op.drop_table("session_cleanup")
