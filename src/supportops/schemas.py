from markdown_it.common.html_re import comment
from httpcore2 import request
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, UTC



#Ticket Schemas
class TicketBase(BaseModel):
    title: str = Field(..., max_length=200, description="Short description of the issue")
    description: str = Field(..., description="Detailed explanation of the issue")
    priority: str | None = Field(default="Medium", max_length=20, description="Business priority")


class TicketCreate(TicketBase):
    category_id: int = Field(..., description="Foreign key to the category table")
    requester_id: int | None = Field(default=None, description="User who reported the issue")


class TicketResponse(TicketBase):
    id: int = Field(..., description="Ticket ID")
    ticket_number: str = Field(..., max_length=20, description="Ticket number")
    status: str = Field(..., max_length=30)
    category_id: int
    requester_id: int | None = None
    assignee_id: int | None = Field(default=None, description="Support engineer currently responsible")
    resolution: str | None = Field(default=None, description="Resolution of the issue")
    created_at: datetime | None = Field(default=None, description="Time when the ticket was created")
    updated_at: datetime | None = Field(default=None, description="Time when the ticket was updated")
    resolved_at: datetime | None = Field(default=None, description="Time when the ticket was resolved")
    closed_at: datetime | None = Field(default=None, description="Time when the ticket was closed")

    model_config = ConfigDict(from_attributes=True)

class TicketAssignment(BaseModel):
    assignee_id: int | None = Field(default=None, description="Support engineer currently responsible")
    
    model_config = ConfigDict(from_attributes=True)

class TicketBasicResponse(TicketBase):
    ticket_number: str = Field(..., max_length=20, description="Ticket number")
    status: str = Field(..., max_length=30)
    requester_id: int = Field(default=None, description="User who reported the issue")
    assignee_id: int = Field(default=None, description="Support engineer currently responsible")
    updated_at: datetime | None = Field(default=None, description="Time when the ticket was updated")
    
    model_config = ConfigDict(from_attributes=True)



class TicketResolution(BaseModel):
    resolution: str | None = Field(default=None, description="Resolution of the issue")

    model_config = ConfigDict(from_attributes=True)

class TicketClosed(BaseModel):
    comment: str = Field(..., description="Comment added by the user")

    model_config = ConfigDict(from_attributes=True)

class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None)
    priority: str | None = Field(default=None, max_length=20)
    category_id: int | None = Field(default=None)
    resolution: str | None = Field(default=None)


class TicketStatusUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=30)
    resolution: str | None = Field(default=None)
    
    model_config = ConfigDict(from_attributes=True)  


class TicketCommentsCreate(BaseModel):
    comment: str = Field(..., description="Comment added by the user")
    commented_by: int | None = Field(default=None, description="User who added the comment")
    
    model_config = ConfigDict(from_attributes=True) 

class TicketCommentsResponse(TicketCommentsCreate):
    id: int = Field(..., description="Comment ID")
    date_time: datetime | None = Field(default=None, description="Time when the comment was added")
    commented_by:int = Field(..., description="User who added the comment")
    ticket_comment: TicketResponse = Field(..., description="Ticket to which the comment was added")
    
    model_config = ConfigDict(from_attributes=True) 


#Category Schemas
class CategoryBase(BaseModel):
    name: str = Field(..., max_length=50, description="Name of the category")
    description: str = Field(..., description="Detailed explanation of the category")


class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int = Field(..., description="Category ID")
    model_config = ConfigDict(from_attributes=True)
    
class CategoryUpdate(BaseModel):
    name: str = Field(..., max_length=50, description="Name of the category")
    description: str = Field(..., description="Detailed explanation of the category")


#User Schemsa
class UserBase(BaseModel):
    username: str = Field(..., max_length=50, description="Username of the user")
    email: str = Field(..., max_length=100, description="Email of the user")
    password: str = Field(..., max_length=255, description="Password of the user")
    role: str = Field(..., max_length=50, description="Role of the user")


class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int = Field(..., description="User ID")
    model_config = ConfigDict(from_attributes=True)
    
class UserUpdate(BaseModel):
    username: str = Field(..., max_length=50, description="Username of the user")
    email: str = Field(..., max_length=100, description="Email of the user")
    password: str = Field(..., max_length=255, description="Password of the user")
    role: str = Field(..., max_length=50, description="Role of the user")