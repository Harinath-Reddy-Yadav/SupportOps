from fastapi import APIRouter, HTTPException, status, Depends, Request
from supportops.schemas import (
    TicketCreate, TicketResponse, TicketAssignment,
    TicketBasicResponse, TicketUpdate, AddTicketComment,
    TicketStatusUpdate, CommentResponse, CommentCreate
)
from supportops.database import get_db
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from sqlalchemy import select, func, or_
import supportops.models as models
import uuid
from datetime import datetime, UTC
from sqlalchemy.exc import IntegrityError
from supportops.auth import CurrentUser, AdminUser, ManagerUser
from supportops.constants import TicketStatusEnum, RoleEnum

router = APIRouter()

# ----------------- 1. Create ticket -----------------
@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED, name="create_ticket", summary="Create a new ticket")
async def create_ticket(ticket: TicketCreate, current_user: CurrentUser,  db:Annotated[AsyncSession, Depends(get_db)]):
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
    new_ticket.status_id = TicketStatusEnum.NEW.value
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

# ----------------- 2. Get all tickets -----------------
@router.get("", response_model=list[TicketBasicResponse], name="get_all_tickets", summary="Get all tickets")
async def get_all_tickets(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    query = (
        select(models.Ticket)
        .options(
            selectinload(models.Ticket.comments).selectinload(models.TicketComments.commented_user)
        )
    )
    is_admin = current_user.role and current_user.role.name.lower() == RoleEnum.ADMIN.value
    # If not admin, only show tickets created by the current user
    if not is_admin:
        query = query.where(models.Ticket.requester_id == current_user.id)
    query = query.order_by(models.Ticket.id.desc())
    results = await db.execute(query)
    tickets = results.scalars().all()
    return tickets
    
# ----------------- 3. Get Assigned Tickets ---------------
@router.get("/assigned", response_model=list[TicketBasicResponse], name="get_assigned_tickets", summary="Get tickets assigned to me or my team")
async def get_assigned_tickets(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    query = (
        select(models.Ticket)
        .options(
            selectinload(models.Ticket.comments).selectinload(models.TicketComments.commented_user)
        )
    )
    user_role = current_user.role.name.lower() if current_user.role else RoleEnum.USER.value
    if user_role == RoleEnum.ADMIN.value:
        # Admin: all assigned tickets
        query = query.where(models.Ticket.assignee_id.is_not(None))
    elif user_role == RoleEnum.MANAGER.value:
        # Manager: tickets assigned to themselves OR any user reporting to them!
        subordinates_subquery = (
            select(models.User.id)
            .where(models.User.manager_id == current_user.id)
        )
        query = query.where(
            or_(
                models.Ticket.assignee_id == current_user.id,
                models.Ticket.assignee_id.in_(subordinates_subquery)
            )
        )
    else:
        # Regular User: tickets assigned directly to them
        query = query.where(models.Ticket.assignee_id == current_user.id)
    query = query.order_by(models.Ticket.id.desc())
    results = await db.execute(query)
    tickets = results.scalars().all()
    return tickets

# ----------------- 4. Get ticket by ID -----------------
@router.get("/{id}", response_model=TicketResponse, name="get_ticket_by_id", summary="Get ticket by ID")
async def get_ticket_by_id(current_user: CurrentUser, id: int, db: Annotated[AsyncSession, Depends(get_db)]):
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

#---------------- 5. Get Ticket by Ticket Number ----------------
@router.get("/ticket/{ticket_number}", response_model=TicketResponse, summary="Get ticket by Ticket Number")
async def get_ticket_by_ticket_number(current_user: CurrentUser, ticket_number: str, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Ticket)
        .options(
            selectinload(models.Ticket.comments)
            .selectinload(models.TicketComments.commented_user)
        )
        .where(models.Ticket.ticket_number == ticket_number)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


# ----------------- 6. Update ticket -----------------
@router.patch("/{id}", response_model=TicketResponse, name="update_ticket", summary="Update ticket")
async def update_ticket(current_user:CurrentUser, id: int, ticket: TicketUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    #Only the user create the ticket and admin can update the ticket
    #Check ticket Exists
    exists = await validate_ticket_exists(id, db)
    if exists:
        try:
            get_ticket = await db.get(models.Ticket,id)
            if current_user.id != get_ticket.requester_id and current_user.role.name.lower() != RoleEnum.ADMIN.value:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to update the ticket")
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


# ----------------- 7. Status update -----------------
@router.post("/{id}/status", response_model=TicketBasicResponse, name="status_update", summary="Update ticket status")
@router.post("/{id}/resolve", response_model=TicketBasicResponse)
@router.post("/{id}/close", response_model=TicketBasicResponse)
async def status_update(id: int, ticket: TicketStatusUpdate, current_user:CurrentUser, request: Request , db: Annotated[AsyncSession, Depends(get_db)]):
    user_role = current_user.role.name.lower() if current_user.role else RoleEnum.USER.value
    # 1. Check ticket exists
    exists = await validate_ticket_exists(id, db)
    if exists:
        get_ticket = await db.get(models.Ticket, id)
        # 2. For /status route only requester and his manager can update the status
        # Get the requester user id and manager id of the user
        user = await db.get(models.User, get_ticket.requester_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requester not found")
        manager_id = user.manager_id

        if request.url.path.endswith("/status"):
            if current_user.id != get_ticket.requester_id and current_user.id != user.manager_id:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to update the ticket status")
    
        # 3. For /resolve and /close only the assignee or assignee manager or admin can update the status
        #get the assignee manager

        if request.url.path.endswith("/resolve") or request.url.path.endswith("/close"):
            if get_ticket.assignee_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot resolve or close an unassigned ticket")
            assignee = await db.get(models.User, get_ticket.assignee_id)
            assignee_manager_id = assignee.manager_id if assignee else None
            if current_user.id != get_ticket.assignee_id and current_user.id != assignee_manager_id and user_role.lower() != RoleEnum.ADMIN.value:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to update the ticket status")
        invalid_status = await validate_ticket_lookups(db, status_id=ticket.status_id)
        if invalid_status:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status {invalid_status}")
        
        if ticket.status_id in [5,6] and not ticket.comments:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment is required for resolved and closed tickets")
        
        result = await db.get(models.Ticket, id)
        result.status_id = ticket.status_id
        if ticket.comments:
            new_comment = AddTicketComment(comment=ticket.comments, user_id=current_user.id, ticket_id=id) # user_id instead of commented_by!
        else:
            new_comment = AddTicketComment(
                comment=f"The status has been updated to {ticket.status_id}",
                user_id=current_user.id,
                ticket_id=id
            )
        await add_ticket_comment(new_comment, db)
        result.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(result, attribute_names=["category_id", "assignee_id", "requester_id","status_id"])
        return result
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

# ----------------- 8. Delete ticket -----------------
@router.delete("/{id}", name="delete_ticket", summary="Delete ticket")
async def delete_ticket(id: int,current_user:CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
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


# ----------------- 9. Assign ticket -----------------
@router.post("/{id}/assign", response_model=TicketBasicResponse, name="assign_ticket", summary="Assign ticket to user")
async def assign_ticket(id: int, current_user: CurrentUser, ticket: TicketAssignment, db: Annotated[AsyncSession, Depends(get_db)]):
    ticket_result = await db.get(models.Ticket, id)
    if not ticket_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    user_role = current_user.role.name.lower() if current_user.role else RoleEnum.USER.value
    target_assignee_id = ticket.assignee_id if ticket.assignee_id is not None else current_user.id
    if target_assignee_id != current_user.id:
        target_user = await db.get(models.User, target_assignee_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee user not found")
        
        # Only Admins, or the direct Manager of the target user, can assign tickets to them
        is_admin = user_role == RoleEnum.ADMIN.value
        is_manager = current_user.id == target_user.manager_id
        if not is_admin and not is_manager:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only assign tickets to yourself or your team members")
    ticket_result.assignee_id = target_assignee_id
    ticket_result.status_id = TicketStatusEnum.ASSIGNED.value
    ticket_result.updated_at = datetime.now(UTC)
    new_comment = AddTicketComment(
        comment=f"Ticket has been assigned to user {target_assignee_id}",
        user_id=current_user.id,
        ticket_id=id
    )
    await add_ticket_comment(new_comment, db)
    await db.commit()
    await db.refresh(ticket_result)
    return ticket_result


# ----------------- 10. Add Comments to ticket -----------------
#Ticket comments
@router.post("/{id}/comments", response_model=CommentResponse, name="add_comment", summary="Add comment to ticket")
async def add_comment(
    id: int,  # <-- Added id from path
    comment: CommentCreate, 
    current_user: CurrentUser, 
    db: Annotated[AsyncSession, Depends(get_db)]
):
    ticket_exists = await validate_ticket_exists(id, db)
    if not ticket_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    new_comment = AddTicketComment(
        comment=comment.comment,
        user_id=current_user.id,
        ticket_id=id
    )
    return await add_ticket_comment(new_comment, db)


# ----------------- Helper functions -----------------
#Validate ticket exists helper function
async def validate_ticket_exists(id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> bool:
    try:
        result = await db.execute(select(models.Ticket).filter(models.Ticket.id == id))
        return result.scalar_one_or_none() is not None
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

#Validate ticket lookups helper function
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