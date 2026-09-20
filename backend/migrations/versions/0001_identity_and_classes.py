"""建立身份、审核、教学班与审计表。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_identity_classes"
down_revision = None
branch_labels = None
depends_on = None

user_type = postgresql.ENUM("STUDENT", "TEACHER", "ADMIN", name="user_type", create_type=False)
user_status = postgresql.ENUM(
    "WAITING_ACTIVATE", "ACTIVATED", "DEACTIVATED", name="user_status", create_type=False
)
review_status = postgresql.ENUM(
    "PENDING", "APPROVED", "REJECTED", name="review_status", create_type=False
)
class_status = postgresql.ENUM("ACTIVE", "ARCHIVED", name="class_status", create_type=False)
member_role = postgresql.ENUM("STUDENT", "TEACHER", name="member_role", create_type=False)


def upgrade() -> None:
    """创建迭代 1 所需数据库对象。"""

    bind = op.get_bind()
    for enum in (user_type, user_status, review_status, class_status, member_role):
        enum.create(bind, checkfirst=True)
    op.create_table(
        "user_account",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("login_name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("phone_number", sa.String(32), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("real_name", sa.String(100), nullable=False),
        sa.Column("user_type", user_type, nullable=False),
        sa.Column("status", user_status, nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True)),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auth_version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("login_name"),
    )
    op.create_index("ix_user_account_login_name", "user_account", ["login_name"])
    op.create_table(
        "student_profile",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_account.id"),
            primary_key=True,
        ),
        sa.Column("student_no", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "teacher_profile",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_account.id"),
            primary_key=True,
        ),
        sa.Column("teacher_no", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "registration_review",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_account.id"),
            nullable=False,
        ),
        sa.Column("status", review_status, nullable=False),
        sa.Column("submitted_profile", postgresql.JSONB(), nullable=False),
        sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_account.id")),
        sa.Column("reason", sa.Text()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_registration_review_user_status", "registration_review", ["user_id", "status"]
    )
    op.create_index(
        "uq_registration_review_pending_user",
        "registration_review",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'::review_status"),
    )
    op.create_table(
        "teaching_class",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "creator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_account.id"),
            nullable=False,
        ),
        sa.Column("status", class_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "class_member",
        sa.Column(
            "class_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teaching_class.id"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_account.id"),
            primary_key=True,
        ),
        sa.Column("role", member_role, nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_account.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("before_data", postgresql.JSONB()),
        sa.Column("after_data", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_event_action", "audit_event", ["action"])
    op.create_index(
        "ix_audit_event_entity", "audit_event", ["entity_type", "entity_id", "created_at"]
    )


def downgrade() -> None:
    """按依赖逆序移除迭代 1 数据库对象。"""

    op.drop_table("audit_event")
    op.drop_table("class_member")
    op.drop_table("teaching_class")
    op.drop_table("registration_review")
    op.drop_table("teacher_profile")
    op.drop_table("student_profile")
    op.drop_table("user_account")
    bind = op.get_bind()
    for enum in (member_role, class_status, review_status, user_status, user_type):
        enum.drop(bind, checkfirst=True)
