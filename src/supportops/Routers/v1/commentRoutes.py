from typing import Annotated
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from supportops.schemas import CommentResponse, CommentUpdate
from supportops.database import get_db
import supportops.models as models
from supportops.auth import CurrentUser
from supportops.constants import RoleEnum

router = APIRouter()


# ----------------- 1. Get comment by ID -----------------
@router.get("/{comment_id}", response_model=CommentResponse, summary="Get comment by ID")
async def get_comment(
    comment_id: int, 
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(models.TicketComments)
        .options(
            selectinload(models.TicketComments.ticket_comment),
            selectinload(models.TicketComments.commented_user)
        )
        .where(models.TicketComments.id == comment_id)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No comment found")
    
    return comment


# ----------------- 2. Get all comments by user -----------------
@router.get("/user/{user_id}", response_model=list[CommentResponse], summary="Get all comments by a user")
async def get_user_comments(
    user_id: int, 
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    user_role = current_user.role.name.lower() if current_user.role else RoleEnum.USER.value
    is_staff = user_role in [RoleEnum.ADMIN.value, RoleEnum.MANAGER.value]

    # Privacy check: users can only view their own comment history unless they are a manager/admin
    if current_user.id != user_id and not is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="You are not authorized to view this user's comments"
        )

    result = await db.execute(
        select(models.TicketComments)
        .options(
            selectinload(models.TicketComments.ticket_comment),
            selectinload(models.TicketComments.commented_user)
        )
        .where(models.TicketComments.commented_by == user_id)
        .order_by(models.TicketComments.id.desc())
    )
    return result.scalars().all()


# ----------------- 3. Update comment -----------------
@router.put("/{comment_id}", response_model=CommentResponse, summary="Update comment text")
async def update_comment(
    comment_id: int,
    comment_update: CommentUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(models.TicketComments)
        .options(
            selectinload(models.TicketComments.ticket_comment),
            selectinload(models.TicketComments.commented_user)
        )
        .where(models.TicketComments.id == comment_id)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No comment found")
    
    # Permission check: Only the comment author or an Admin can edit it
    is_admin = current_user.role and current_user.role.name.lower() == RoleEnum.ADMIN.value
    if comment.commented_by != current_user.id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own comments"
        )

    comment.comment = comment_update.comment
    try:
        await db.commit()
        await db.refresh(comment)
        return comment
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update comment")


# ----------------- 4. Delete comment -----------------
@router.delete("/{comment_id}", status_code=status.HTTP_200_OK, summary="Delete comment")
async def delete_comment(
    comment_id: int, 
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    comment = await db.get(models.TicketComments, comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No comment found")
    
    # Permission check: Only the comment author or an Admin can delete it
    is_admin = current_user.role and current_user.role.name.lower() == RoleEnum.ADMIN.value
    if comment.commented_by != current_user.id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments"
        )

    try:
        await db.delete(comment)
        await db.commit()
        return {"message": f"Deleted comment {comment_id} successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete comment")\


# ----------------- 5. Get all comments for a ticket -----------------
@router.get("/ticket/{ticket_id}", response_model=list[CommentResponse], summary="Get all comments for a ticket")
async def get_ticket_comments(
    ticket_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    ticket = await db.get(models.Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    result = await db.execute(
        select(models.TicketComments)
        .options(
            selectinload(models.TicketComments.ticket_comment),
            selectinload(models.TicketComments.commented_user)
        )
        .where(models.TicketComments.ticket_id == ticket_id)
        .order_by(models.TicketComments.id.asc())
    )
    return result.scalars().all()