import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    DateTime,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


def now_utc():
    return datetime.now(timezone.utc)


def gen_invite_code():
    return uuid.uuid4().hex[:10]


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=now_utc)

    memberships = relationship("GroupMember", back_populates="user")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    invite_code = Column(
        String(32), unique=True, index=True, default=gen_invite_code
    )
    currency = Column(String(3), nullable=False, default="RUB", server_default="RUB")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now_utc)

    members = relationship(
        "GroupMember", back_populates="group", cascade="all, delete-orphan"
    )
    expenses = relationship(
        "Expense", back_populates="group", cascade="all, delete-orphan"
    )


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_user"),)

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=now_utc)

    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="memberships")


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    description = Column(String(256), nullable=False)
    amount = Column(Float, nullable=False)
    paid_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=now_utc)

    group = relationship("Group", back_populates="expenses")
    paid_by = relationship("User", foreign_keys=[paid_by_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    shares = relationship(
        "ExpenseShare", back_populates="expense", cascade="all, delete-orphan"
    )


class ExpenseShare(Base):
    __tablename__ = "expense_shares"

    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(Integer, ForeignKey("expenses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    share_amount = Column(Float, nullable=False)

    expense = relationship("Expense", back_populates="shares")
    user = relationship("User")
