"""持久运行日志与全局日志设置。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0016_system_logs"
down_revision = "0015_mistake_annotations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "log_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_enabled", sa.Boolean(), nullable=False),
        sa.Column("debug_modules", postgresql.JSONB(), nullable=False),
    )
    op.bulk_insert(
        sa.table(
            "log_settings",
            sa.column("id", sa.Integer()),
            sa.column("file_enabled", sa.Boolean()),
            sa.column("debug_modules", postgresql.JSONB()),
        ),
        [{"id": 1, "file_enabled": False, "debug_modules": {}}],
    )
    op.create_table(
        "runtime_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("level", sa.String(10), nullable=False),
        sa.Column("module", sa.String(100), nullable=False),
        sa.Column("task", sa.String(100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.String(100)),
    )
    op.create_index("ix_runtime_log_module", "runtime_log", ["module"])
    op.create_index("ix_runtime_log_correlation_id", "runtime_log", ["correlation_id"])


def downgrade():
    op.drop_table("runtime_log")
    op.drop_table("log_settings")
