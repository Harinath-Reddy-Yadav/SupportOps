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
    status_id: Mapped[int] = mapped_column(ForeignKey("status.id"), nullable=False) #New, Assigned, In Progress, On Hold, Resolved, Closed, Reopened
    priority_id: Mapped[int] = mapped_column(ForeignKey("priorities.id"), nullable=False) #Low, Medium, High, Critical
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    category: Mapped[Category] = relationship(back_populates="tickets")
    requester: Mapped[User] = relationship(back_populates="requested_tickets", foreign_keys=[requester_id])
    assignee: Mapped[User | None] = relationship(back_populates="assigned_tickets", foreign_keys=[assignee_id])
    comments: Mapped[list[TicketComments]] = relationship(back_populates="ticket_comment", order_by="TicketComments.id")
    
    ticket_priority: Mapped[Priority] = relationship(back_populates="ticket_pri")
    ticket_status: Mapped[Status] = relationship(back_populates="ticket_stat")



class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    last_logged_in: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    profile_pic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True) 

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def role_name(self) -> str | None:
        return self.role.name if self.role else None

    @property
    def image_path(self) -> str | None:
        return f"/media/profile_pics/{self.profile_pic}" if self.profile_pic else None

    manager: Mapped[User | None] = relationship(
        "User",
        remote_side="User.id",
        backref="subordinates"
    )

    # Separate relationships for requester vs assignee
    requested_tickets: Mapped[list[Ticket]] = relationship(back_populates="requester", foreign_keys="[Ticket.requester_id]")
    assigned_tickets: Mapped[list[Ticket]] = relationship(back_populates="assignee", foreign_keys="[Ticket.assignee_id]")
    comments: Mapped[list[TicketComments]] = relationship(back_populates="commented_user")
    role: Mapped[Role] = relationship(back_populates="users")



class TicketComments(Base):
    __tablename__ = "TicketComments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    date_time: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    commented_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    @property
    def ticket_number(self) -> str | None:
        return self.ticket_comment.ticket_number if self.ticket_comment else None

    ticket_comment: Mapped[Ticket] = relationship(back_populates="comments")

    commented_user: Mapped[User] = relationship(back_populates="comments")


class Priority(Base):
    __tablename__ = "priorities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    ticket_pri: Mapped[list[Ticket]] = relationship(back_populates="ticket_priority")


class Status(Base):
    __tablename__ = "status"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    ticket_stat: Mapped[list[Ticket]] = relationship(back_populates="ticket_status")


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False) #"customer", "agent", "manager", "admin"
    description: Mapped[str] = mapped_column(Text, nullable=True)

    users: Mapped[list[User]] = relationship(back_populates="role")