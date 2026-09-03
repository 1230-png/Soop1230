"""초기 스키마.

Revision ID: 0001
Create Date: 2026-08-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topic_categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("label_ko", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "scripts",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "topic_category_id",
            sa.Integer,
            sa.ForeignKey("topic_categories.id"),
            nullable=False,
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("hook", sa.Text, nullable=False),
        sa.Column("body", postgresql.JSONB, nullable=False),
        sa.Column("cta_question", sa.Text, nullable=False),
        sa.Column("image_query", sa.Text, nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column(
            "excluded_topics", postgresql.JSONB, nullable=False, server_default="[]"
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("claimed_by", sa.String(128)),
        sa.CheckConstraint(
            "status IN ('pending','rendering','rendered','uploaded','failed')",
            name="ck_scripts_status",
        ),
    )
    op.create_index("ix_scripts_topic_category_id", "scripts", ["topic_category_id"])
    # 큐에서 꺼낼 때만 쓰는 인덱스라 부분 인덱스로 작게 유지한다.
    op.create_index(
        "idx_scripts_pending",
        "scripts",
        ["created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "videos",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "script_id",
            sa.BigInteger,
            sa.ForeignKey("scripts.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("youtube_video_id", sa.String(32), nullable=False, unique=True),
        sa.Column(
            "topic_category_id",
            sa.Integer,
            sa.ForeignKey("topic_categories.id"),
            nullable=False,
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("duration_sec", sa.Numeric(6, 2), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_videos_topic_category_id", "videos", ["topic_category_id"])

    op.create_table(
        "video_metrics",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "video_id",
            sa.BigInteger,
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("view_count", sa.BigInteger, nullable=False),
        sa.Column("like_count", sa.BigInteger, nullable=False),
        sa.Column("comment_count", sa.BigInteger, nullable=False),
        sa.Column("avg_view_pct", sa.Numeric(5, 2)),
        # 계산을 DB 한 곳에 둔다. 조회수 0이면 NULL이 되어 집계에서 자동으로 빠진다.
        sa.Column(
            "like_ratio",
            sa.Numeric(6, 5),
            sa.Computed("like_count::numeric / NULLIF(view_count, 0)", persisted=True),
        ),
        sa.UniqueConstraint("video_id", "fetched_at", name="uq_metric_snapshot"),
        sa.CheckConstraint("view_count >= 0", name="ck_metrics_views_nonneg"),
        sa.CheckConstraint("like_count >= 0", name="ck_metrics_likes_nonneg"),
    )
    op.create_index(
        "idx_metrics_latest",
        "video_metrics",
        ["video_id", sa.text("fetched_at DESC")],
    )

    # 스냅샷이 계속 쌓이므로, 그냥 조인하면 오래된 값까지 평균에 섞인다.
    op.execute(
        """
        CREATE VIEW v_latest_metrics AS
        SELECT DISTINCT ON (video_id)
               id, video_id, fetched_at, view_count, like_count,
               comment_count, avg_view_pct, like_ratio
        FROM video_metrics
        ORDER BY video_id, fetched_at DESC
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_latest_metrics")
    op.drop_table("video_metrics")
    op.drop_table("videos")
    op.drop_table("scripts")
    op.drop_table("topic_categories")
