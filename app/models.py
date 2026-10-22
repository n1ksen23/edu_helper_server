from datetime import datetime, date, timezone
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from .config import settings


class Base(DeclarativeBase):
    pass


def now():
    return datetime.now(timezone.utc)


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    password_hash: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(80), default="Europe/Moscow")
    anchor_monday: Mapped[date] = mapped_column(Date, default=date(2026, 10, 19))
    anchor_week: Mapped[str] = mapped_column(String(5), default="lower")


class Homework(Base):
    __tablename__ = "homework"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    subject: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date] = mapped_column(Date)
    legacy_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
    __table_args__ = (
        Index("ix_homework_group_due_id", "group_id", "due_date", "id"),
        UniqueConstraint("group_id", "legacy_id"),
    )


class Day(Base):
    __tablename__ = "days"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date)
    shortened: Mapped[bool] = mapped_column(Boolean)
    lessons: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (UniqueConstraint("group_id", "date"),)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(10))
    refresh_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class GroupRequest(Base):
    __tablename__ = "group_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_number: Mapped[str] = mapped_column(String(50))
    contacts: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        Index("ix_group_requests_status_id", "status", "id"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')"),
    )


engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def db():
    async with SessionLocal() as session:
        yield session
