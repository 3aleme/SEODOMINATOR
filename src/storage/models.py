"""SQLAlchemy ORM models for SEODOMINATOR."""

from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Run(Base):
    """One full 12-stage pipeline execution."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    seed_keywords: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    config: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON overrides
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list["StepLog"]] = relationship(
        "StepLog", back_populates="run", cascade="all, delete-orphan", order_by="StepLog.started_at"
    )
    blog_post: Mapped["BlogPost | None"] = relationship(
        "BlogPost", back_populates="run", uselist=False, cascade="all, delete-orphan"
    )


class StepLog(Base):
    """Output of one pipeline stage within a run."""

    __tablename__ = "step_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped["Run"] = relationship("Run", back_populates="steps")


class BlogPost(Base):
    """Final content product — one per run."""

    __tablename__ = "blog_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    seo_tags: Mapped[str | None] = mapped_column(Text, nullable=True)       # JSON array
    image_urls: Mapped[str | None] = mapped_column(Text, nullable=True)     # JSON array (hero + in-article)
    published_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    keyword_density: Mapped[float | None] = mapped_column(Float, nullable=True)
    internal_links: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    run: Mapped["Run"] = relationship("Run", back_populates="blog_post")
    keyword_tracking: Mapped[list["KeywordTracking"]] = relationship(
        "KeywordTracking", back_populates="blog_post", cascade="all, delete-orphan"
    )


class KeywordTracking(Base):
    """Per-keyword ranking tracking — populated by Step 12, updated periodically."""

    __tablename__ = "keyword_tracking"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(500), nullable=False)
    blog_post_id: Mapped[int | None] = mapped_column(ForeignKey("blog_posts.id"), nullable=True)
    published_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    target_position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ctr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_position: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    blog_post: Mapped["BlogPost | None"] = relationship("BlogPost", back_populates="keyword_tracking")


class InternalLink(Base):
    """Internal link graph — one row per directed source→target link."""

    __tablename__ = "internal_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_slug: Mapped[str] = mapped_column(String(200), nullable=False)
    target_slug: Mapped[str] = mapped_column(String(200), nullable=False)
    anchor_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_run: Mapped[int | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("source_slug", "target_slug", name="uq_internal_link"),
    )
