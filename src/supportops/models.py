from  __future__ import annotations
from datetime import UTC, datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Column, Integer, String, ForeignKey, Text, Boolean, DateTime
from .database import Base

class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    tickets: Mapped[list[Ticket]] = relationship(back_populates="category")


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticket_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="New")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="Medium")
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    category: Mapped[Category] = relationship(back_populates="tickets")
    requester: Mapped[User] = relationship(back_populates="requested_tickets", foreign_keys=[requester_id])
    assignee: Mapped[User | None] = relationship(back_populates="assigned_tickets", foreign_keys=[assignee_id])
    comments: Mapped[list[TicketComments]] = relationship(back_populates="ticket_comment")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="Customer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    last_logged_in: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Separate relationships for requester vs assignee
    requested_tickets: Mapped[list[Ticket]] = relationship(back_populates="requester", foreign_keys="[Ticket.requester_id]")
    assigned_tickets: Mapped[list[Ticket]] = relationship(back_populates="assignee", foreign_keys="[Ticket.assignee_id]")
    comments: Mapped[list[TicketComments]] = relationship(back_populates="commented_user")



class TicketComments(Base):
    __tablename__ = "TicketComments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    date_time: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    commented_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    ticket_comment: Mapped[Ticket] = relationship(back_populates="comments")

    commented_user: Mapped[User] = relationship(back_populates="comments")