from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, Enum, ForeignKey,
    Integer, String, Text, Time, Float
)
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    child = "child"
    parent = "parent"


class TaskCategory(str, enum.Enum):
    home = "home"
    school = "school"
    personal = "personal"
    weekly = "weekly"


class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RecurType(str, enum.Enum):
    daily = "daily"
    weekday = "weekday"
    weekly = "weekly"
    once = "once"


class RecurTime(str, enum.Enum):
    morning = "morning"
    evening = "evening"
    specific = "specific"


class CompletionStatus(str, enum.Enum):
    pending = "pending"
    done = "done"
    skipped = "skipped"
    postponed = "postponed"


class RewardType(str, enum.Enum):
    real = "real"
    virtual = "virtual"


class RewardRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class PostponeStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ParentRole(str, enum.Enum):
    mom = "mom"
    dad = "dad"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    role = Column(Enum(UserRole), nullable=False)
    parent_role = Column(Enum(ParentRole), nullable=True)
    name = Column(String(100), nullable=False)
    morning_time = Column(String(5), default="07:30")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    category = Column(Enum(TaskCategory), nullable=False, default=TaskCategory.personal)
    priority = Column(Enum(TaskPriority), nullable=False, default=TaskPriority.medium)
    is_critical = Column(Boolean, default=False)
    is_recurring = Column(Boolean, default=False)
    recur_type = Column(Enum(RecurType), nullable=True)
    recur_time = Column(Enum(RecurTime), nullable=True)
    deadline = Column(Date, nullable=True)
    specific_time = Column(String(5), nullable=True)
    points = Column(Integer, default=1)
    penalty_points = Column(Integer, default=0)
    created_by = Column(BigInteger, nullable=True)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    subtasks = relationship("Subtask", back_populates="task", cascade="all, delete-orphan")
    completions = relationship("TaskCompletion", back_populates="task", cascade="all, delete-orphan")
    postpone_requests = relationship("PostponeRequest", back_populates="task", cascade="all, delete-orphan")


class Subtask(Base):
    __tablename__ = "subtasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    is_done = Column(Boolean, default=False)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="subtasks")


class TaskCompletion(Base):
    __tablename__ = "task_completions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(Enum(CompletionStatus), default=CompletionStatus.pending)
    postpone_reason = Column(Text, nullable=True)
    postponed_to = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="completions")
    postpone_requests = relationship("PostponeRequest", back_populates="completion", cascade="all, delete-orphan")


class Points(Base):
    __tablename__ = "points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    balance = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PointsHistory(Base):
    __tablename__ = "points_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    reason = Column(String(300), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Reward(Base):
    __tablename__ = "rewards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    cost_points = Column(Integer, nullable=False)
    reward_type = Column(Enum(RewardType), nullable=False, default=RewardType.real)
    max_price = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    requests = relationship("RewardRequest", back_populates="reward", cascade="all, delete-orphan")


class RewardRequest(Base):
    __tablename__ = "reward_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reward_id = Column(Integer, ForeignKey("rewards.id", ondelete="CASCADE"), nullable=False)
    telegram_id = Column(BigInteger, nullable=False)
    status = Column(Enum(RewardRequestStatus), default=RewardRequestStatus.pending)
    week_start = Column(Date, nullable=True)
    requested_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    reward = relationship("Reward", back_populates="requests")


class ScheduleBlock(Base):
    __tablename__ = "schedule_blocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    day_of_week = Column(Integer, nullable=True)  # 0=Mon, 6=Sun, None=all
    blocked_from = Column(String(5), nullable=False)  # "HH:MM"
    blocked_to = Column(String(5), nullable=False)    # "HH:MM"
    event_name = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BotSettings(Base):
    __tablename__ = "bot_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(String(500), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PostponeRequest(Base):
    __tablename__ = "postpone_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    completion_id = Column(Integer, ForeignKey("task_completions.id", ondelete="CASCADE"), nullable=True)
    reason = Column(Text, nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(PostponeStatus), default=PostponeStatus.pending)
    resolved_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="postpone_requests")
    completion = relationship("TaskCompletion", back_populates="postpone_requests")
