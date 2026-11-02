"""为已提交操作审计分配有序公开游标。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0017_audit_publication"
down_revision = "0016_system_logs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("audit_publication_state", sa.Column("id", sa.Integer(), primary_key=True))
    op.bulk_insert(sa.table("audit_publication_state", sa.column("id", sa.Integer())), [{"id": 1}])
    op.create_table(
        "audit_publication",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit_event.id"),
            nullable=False,
        ),
        sa.UniqueConstraint("event_id"),
    )


def downgrade():
    op.drop_table("audit_publication")
    op.drop_table("audit_publication_state")
