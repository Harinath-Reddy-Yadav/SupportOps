from fastapi import APIRouter, HTTPException, status, Depends
from supportops.schemas import (
    TicketCreate, TicketResponse, TicketAssignment,
    TicketBasicResponse, TicketUpdate, AddTicketComment,
    TicketStatusUpdate, CommentResponse, CommentCreate
)
from supportops.database import get_db
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from sqlalchemy import select, func
import supportops.models as models
import uuid
from datetime import datetime, UTC
from sqlalchemy.exc import IntegrityError
from supportops.auth import get_current_user

router = APIRouter()

# ----------------- Create ticket -----------------
@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED, name="create_ticket", summary="Create a new ticket")
async def create_ticket(ticket: TicketCreate, current_user: Annotated[models.User, Depends(get_current_user)],  db:Annotated[AsyncSession, Depends(get_db)]):
    #Validate inputs
    invalid = await validate_ticket_lookups(
        db,
        category_id=ticket.category_id,
        priority_id=ticket.priority_id,
        requester_id=current_user.id,
    )
    

    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"detail": "Invalid reference values", "invalid": invalid},
        )
    
    #Adding the backend values to the ticket
    max_id_result = await db.execute(select(models.Ticket.id).order_by(models.Ticket.id.desc()).limit(1))
    max_id = max_id_result.scalar_one_or_none()
    if max_id is None:
        max_id = 1
    else:
        max_id = max_id + 1

    new_ticket = models.Ticket(**ticket.model_dump())
    new_ticket.requester_id = current_user.id
    new_ticket.id = max_id
    new_ticket.ticket_number = "TKT"+str(uuid.uuid1().hex)[:16]
    new_ticket.created_at = datetime.now(UTC)
    new_ticket.updated_at = datetime.now(UTC)
    new_ticket.status_id = 1
    try:
        db.add(new_ticket)
        await db.commit()
        await db.refresh(new_ticket)
        return new_ticket
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid data")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="Internal server error occured")

# ----------------- Get all tickets -----------------
@router.get("", response_model=list[TicketBasicResponse], name="get_all_tickets", summary="Get all tickets")
async def get_all_tickets(db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        results = await db.execute(select(models.Ticket)
                            .options(
                                selectinload(models.Ticket.comments)
                                .selectinload(models.TicketComments.commented_user)
                            )
                            .order_by(models.Ticket.id))
        tickets = results.scalars().all()
        
        response = []
        for ticket in tickets:
            ticket_data = TicketResponse.model_validate(ticket)
            if ticket_data.comments:
                ticket_data.comments = ticket_data.comments[-5:]
            response.append(ticket_data)
        return response
    except Exception as e:
        raise HTTPException(status_code= status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server error Occured")


# ----------------- Get ticket by ID -----------------
@router.get("/{id}", response_model=TicketResponse, name="get_ticket_by_id", summary="Get ticket by ID")
async def get_ticket_by_id(id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    #validate the ticket Id exits
    exists = await validate_ticket_exists(id, db)
    if exists:
        try:
            result = await db.execute(
                select(models.Ticket)
                .options(
                    selectinload(models.Ticket.comments)
                    .selectinload(models.TicketComments.commented_user)
                )
                .where(models.Ticket.id == id)
            )
            ticket = result.scalar_one_or_none()
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error occured")
        if ticket is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket



# ----------------- Update ticket -----------------
@router.patch("/{id}", response_model=TicketResponse, name="update_ticket", summary="Update ticket")
async def update_ticket(id: int, ticket: TicketUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    #validate ticket exists
    exists = await validate_ticket_exists(id, db)
    if exists:
        try:
            #validate Priority and Category if provided
            if ticket.priority_id is not None or ticket.category_id is not None:
                invalid = await validate_ticket_lookups(
                    db,
                    priority_id=ticket.priority_id,
                    category_id=ticket.category_id,
                )

                if invalid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"detail": "Invalid reference values", "invalid": invalid},
                    )

            ticket_result = await db.get(models.Ticket, id)
            update_data = ticket.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(ticket_result, key, value)  ## Another way of keyword mapping for databse insertion
            ticket_result.updated_at = datetime.now(UTC)
            await db.commit()
            await db.refresh(ticket_result, attribute_names=["category_id", "assignee_id", "requester_id","status_id","category_id"])
            return ticket_result

        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")


# ----------------- Delete ticket -----------------
@router.delete("/{id}", name="delete_ticket", summary="Delete ticket")
async def delete_ticket(id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    #validate the ticket Id exists
    exists = await validate_ticket_exists(id, db)
    if exists:
        try:
            ticket = await db.get(models.Ticket, id)
            #Delete the related comments in the db
            comments = await db.execute(select(models.TicketComments).where(models.TicketComments.ticket_id == id))
            for comment in comments.scalars().all():
                await db.delete(comment)
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        await db.delete(ticket)
        await db.commit()
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return {"message": f"Ticket {ticket.ticket_number} deleted successfully"}


# ----------------- Assign ticket -----------------
@router.post("/{id}/assign", response_model=TicketBasicResponse, name="assign_ticket", summary="Assign ticket to user")
async def assign_ticket(id: int, ticket: TicketAssignment, db: Annotated[AsyncSession, Depends(get_db)]):
    exists = await validate_ticket_exists(id, db)
    if exists:
        ticket_result = await db.get(models.Ticket,id)
        update_data = ticket.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(ticket_result, key, value)
        ticket_result.updated_at = datetime.now(UTC)
        ticket_result.status_id = 2
        await db.commit()
        await db.refresh(ticket_result, attribute_names=["category_id", "assignee_id", "requester_id","status_id","category_id"])
        return ticket_result
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")


# ----------------- Status update -----------------
@router.post("/{id}/status", response_model=TicketBasicResponse, name="status_update", summary="Update ticket status")
@router.post("/{id}/resolve", response_model=TicketBasicResponse)
@router.post("/{id}/close", response_model=TicketBasicResponse)
async def status_update(id: int, ticket: TicketStatusUpdate, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    exists = await validate_ticket_exists(id, db)
    if exists:
        #verify ticket status_id is valid and comment is not none for closed and resolved
        invalid_status = await validate_ticket_lookups(db, status_id=ticket.status_id)
        if invalid_status:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status {invalid_status}")
        
        if ticket.status_id in [5,6] and not ticket.comments:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment is required for resolved and closed tickets")
        
        result = await db.get(models.Ticket, id)
        result.status_id = ticket.status_id
        if ticket.comments:
            new_comment = AddTicketComment(comment=ticket.comments, commented_by=current_user.id, ticket_id=id)
        else:
            new_comment = f"The status has been updated from {result.status_id} to {ticket.status_id}"
        await add_ticket_comment(new_comment, db)
        result.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(result, attribute_names=["category_id", "assignee_id", "requester_id","status_id"])
        return result
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")


# ----------------- Add Comments to ticket -----------------
#Ticket comments
@router.post("/{id}/comments", response_model=CommentResponse, name="add_comment", summary="Add comment to ticket")
async def add_comment(comment: CommentCreate, current_user: Annotated[models.User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        if comment.comment is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment is required")
        if comment.ticket_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ticket ID is required")

        new_comment = AddTicketComment(comment=comment.comment, commented_by=current_user.id, ticket_id=id)
        add_comment = await add_ticket_comment(new_comment, db)
        return add_comment

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add comment")


# ----------------- Helper functions -----------------
#Validate ticket exists helper function
async def validate_ticket_exists(id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> bool:
    try:
        result = await db.execute(select(models.Ticket).filter(models.Ticket.id == id))
        return result.scalar_one_or_none() is not None
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
async def validate_ticket_lookups(
    db: AsyncSession,
    category_id: int | None = None,
    priority_id: int | None = None,
    requester_id: int | None = None,
    assignee_id: int | None = None,
    status_id: int | None = None,
    role_id: int | None = None,
) -> list[str]:
    invalid_fields: list[str] = []

    if category_id is not None and not await db.get(models.Category, category_id):
        invalid_fields.append(f"Category with id {category_id} not found")
    if priority_id is not None and not await db.get(models.Priority, priority_id):
        invalid_fields.append(f"Priority with id {priority_id} not found")
    if requester_id is not None and not await db.get(models.User, requester_id):
        invalid_fields.append(f"Requester user with id {requester_id} not found")
    if assignee_id is not None and not await db.get(models.User, assignee_id):
        invalid_fields.append(f"Assignee user with id {assignee_id} not found")
    if status_id is not None and not await db.get(models.Status, status_id):
        invalid_fields.append(f"Status with id {status_id} not found")
    if role_id is not None and not await db.get(models.Role, role_id):
        invalid_fields.append(f"Role with id {role_id} not found")

    return invalid_fields


async def add_ticket_comment(comment: AddTicketComment, db: AsyncSession):
    try:
        new_comment = models.TicketComments(
            ticket_id=comment.ticket_id,
            comment=comment.comment,
            commented_by=comment.user_id,
            date_time=datetime.now(UTC),
        )
        db.add(new_comment)
        await db.commit()
        await db.refresh(new_comment)
        return new_comment
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))