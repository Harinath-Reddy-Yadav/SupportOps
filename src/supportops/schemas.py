from pydantic import BaseModel, Field, ConfigDict, EmailStr
from datetime import datetime


# ==========================================
# 1. Lookup / Support Schemas
# ==========================================

# Role Schemas
class RoleBase(BaseModel):
    name: str = Field(..., max_length=50, description="Name of the role")
    description: str = Field(..., description="Detailed explanation of the role")

class RoleCreate(RoleBase):
    pass

class RoleResponse(RoleBase):
    id: int = Field(..., description="Role ID")
    model_config = ConfigDict(from_attributes=True)


# Category Schemas
class CategoryBase(BaseModel):
    name: str = Field(..., max_length=50, description="Name of the category")
    description: str = Field(..., description="Detailed explanation of the category")

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int = Field(..., description="Category ID")
    model_config = ConfigDict(from_attributes=True)

class ReassignCategoryTickets(BaseModel):
    new_category_id: int = Field(..., description="Target category ID to move tickets to")


# Priority Schemas
class PriorityBase(BaseModel):
    name: str = Field(..., max_length=50, description="Name of the priority")
    description: str = Field(..., description="Detailed explanation of the priority")

class PriorityCreate(PriorityBase):
    pass

class PriorityResponse(PriorityBase):
    id: int = Field(..., description="Priority ID")
    model_config = ConfigDict(from_attributes=True)


# Status Schemas
class StatusBase(BaseModel):
    name: str = Field(..., max_length=50, description="Name of the status")
    description: str = Field(..., description="Detailed explanation of the status")

class StatusCreate(StatusBase):
    pass

class StatusResponse(StatusBase):
    id: int = Field(..., description="Status ID")
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 2. User Schemas
# ==========================================

class UserBase(BaseModel):
    username: str = Field(..., max_length=50, description="Username of the user")

class UserCreate(UserBase):
    first_name: str = Field(..., max_length=100, description="First name of the user")
    last_name: str = Field(..., max_length=100, description="Last name of the user")
    email: EmailStr = Field(..., description="Email of the user")
    password_hash: str = Field(..., max_length=255, description="Password of the user")

class UserPrivateCreate(UserCreate):
    role_id: int = Field(default=1, description="Role of the user")
    manager_id: int | None = Field(default=None, description="Manager ID of the user")

class UserShortResponse(BaseModel):
    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username of the user")
    full_name: str = Field(..., description="Full name of the user")
    model_config = ConfigDict(from_attributes=True)

class UserPublicResponse(UserShortResponse):
    role_name: str | None = Field(default=None, description="Role name of the user")
    model_config = ConfigDict(from_attributes=True)

class UserResponse(UserPublicResponse):
    email: EmailStr = Field(..., description="Email of the user")
    manager_id: int | None = Field(default=None, description="Manager ID of the user")
    manager: UserShortResponse | None = Field(default=None, description="Manager of the user")
    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    username: str | None = Field(default=None, max_length=50, description="Username of the user")
    first_name: str | None = Field(default=None, max_length=100, description="First name of the user")
    last_name: str | None = Field(default=None, max_length=100, description="Last name of the user")
    email: EmailStr | None = Field(default=None, description="Email of the user")
    password: str | None = Field(default=None, max_length=255, description="Password of the user")

class UserRoleUpdate(BaseModel):
    role_id: int | None = Field(default=None, description="Role ID of the user")


# ==========================================
# 3. Comment Schemas
# ==========================================

class CommentBase(BaseModel):
    comment: str = Field(..., description="Comment added by the user")

class CommentCreate(CommentBase):
    pass

class AddTicketComment(BaseModel):
    comment: str | None = Field(default=None, description="Comment added by the user")
    ticket_id: int = Field(..., description="Ticket to which the comment was added")
    user_id: int = Field(..., description="User who added the comment")
    model_config = ConfigDict(from_attributes=True)

class CommentResponseWithTicket(BaseModel):
    id: int = Field(..., description="Comment ID")
    ticket_number: str = Field(..., description="Ticket number")
    date_time: datetime | None = Field(default=None, description="Time when the comment was added")
    commented_user: UserShortResponse = Field(..., description="User who added the comment")

    model_config = ConfigDict(from_attributes=True)

class CommentResponse(CommentResponseWithTicket):
    ticket_id: int = Field(..., description="Ticket to which the comment was added")
    model_config = ConfigDict(from_attributes=True)

class CommentUpdate(CommentBase):
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 4. Ticket Schemas
# ==========================================

class TicketBase(BaseModel):
    title: str = Field(..., max_length=200, description="Short description of the issue")
    description: str = Field(..., description="Detailed explanation of the issue")

class TicketCreate(TicketBase):
    priority_id: int = Field(..., description="Priority of the ticket")
    category_id: int = Field(..., description="Category of the ticket")

class TicketBasicResponse(TicketBase):
    id: int = Field(..., description="Ticket ID")
    ticket_number: str = Field(..., max_length=20, description="Ticket number")
    requester: UserShortResponse | None = Field(default=None, description="User who reported the issue")
    assignee: UserShortResponse | None = Field(default=None, description="Support engineer currently responsible")
    ticket_status: StatusResponse = Field(..., description="Status of the ticket")
    created_at: datetime | None = Field(default=None, description="Time when the ticket was created")
    updated_at: datetime | None = Field(default=None, description="Time when the ticket was updated")
    
    model_config = ConfigDict(from_attributes=True)

class TicketResponse(TicketBasicResponse):
    ticket_priority: PriorityResponse = Field(..., description="Business priority")
    category: CategoryResponse = Field(..., description="Category of the ticket")
    closed_at: datetime | None = Field(default=None, description="Time when the ticket was closed")
    comments: list[CommentResponseWithTicket] = Field(default_factory=list, description="Comments added to the ticket")

    model_config = ConfigDict(from_attributes=True)

class TicketAssignment(BaseModel):
    assignee_id: int | None = Field(default=None, description="Support engineer currently responsible")
    model_config = ConfigDict(from_attributes=True)

class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None)
    priority_id: int | None = Field(default=None)
    category_id: int | None = Field(default=None)

class TicketStatusUpdate(BaseModel):
    status_id: int = Field(..., description="Status of the ticket")
    comments: str | None = Field(default=None)
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 5. Token Schemas for Authentication
# ==========================================

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None

class TokenPayload(BaseModel):
    sub: str | None = None
