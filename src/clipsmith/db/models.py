"""SQLAlchemy ORM models: Run, Clip, PipelineEvent."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Enum as SAEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vod_id: Mapped[str] = mapped_column(String(64), index=True)
    channel: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[RunStatus] = mapped_column(SAEnum(RunStatus), default=RunStatus.pending)
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    clips: Mapped[list[Clip]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="select"
    )
    events: Mapped[list[PipelineEvent]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="select"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vod_id": self.vod_id,
            "channel": self.channel,
            "status": self.status.value,
            "stage": self.stage,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "clip_count": len(self.clips),
        }


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("runs.id"), index=True)
    filename: Mapped[str] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(String(256), default="")
    start_s: Mapped[float] = mapped_column(Float, default=0.0)
    end_s: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    published_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    run: Mapped[Run] = relationship(back_populates="clips")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "filename": self.filename,
            "title": self.title,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "score": self.score,
            "approved": self.approved,
            "published_url": self.published_url,
            "created_at": self.created_at.isoformat(),
        }


class PipelineEvent(Base):
    __tablename__ = "pipeline_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("runs.id"), index=True)
    stage: Mapped[str] = mapped_column(String(64))
    pct: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=_now)

    run: Mapped[Run] = relationship(back_populates="events")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "stage": self.stage,
            "pct": self.pct,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
        }
