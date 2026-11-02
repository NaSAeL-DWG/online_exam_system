"""索引未发布审计，避免永久审计全表扫描。"""

from alembic import op
import sqlalchemy as sa

revision = "0018_audit_pending_index"
down_revision = "0017_audit_publication"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "audit_event",
        sa.Column("log_published", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    events = sa.table("audit_event", sa.column("id"), sa.column("log_published", sa.Boolean()))
    published = sa.table("audit_publication", sa.column("event_id"))
    op.execute(
        events.update()
        .where(
            sa.exists(sa.select(published.c.event_id).where(published.c.event_id == events.c.id))
        )
        .values(log_published=True)
    )
    op.create_index(
        "ix_audit_event_unpublished",
        "audit_event",
        ["created_at", "id"],
        postgresql_where=sa.text("log_published = false"),
    )


def downgrade():
    op.drop_index("ix_audit_event_unpublished", table_name="audit_event")
    op.drop_column("audit_event", "log_published")
