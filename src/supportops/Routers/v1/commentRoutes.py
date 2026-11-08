from fastapi import APIRouter, HTTPException, status, Depends
from supportops.schemas import CommentResponse, CommentUpdate
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated
from supportops.database import get_db
import supportops.models as models

router = APIRouter()


# ----------------- Get comment by id -----------------
@router.get("/{comment_id}", response_model=CommentResponse, summary="Get comment by ID")
async def get_comment(comment_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
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


# ----------------- Get all comments by user -----------------
@router.get("/user/{user_id}", response_model=list[CommentResponse], summary="Get all comments by a user")
async def get_user_comments(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.TicketComments)
        .options(
            selectinload(models.TicketComments.ticket_comment),
            selectinload(models.TicketComments.commented_user)
        )
        .where(models.TicketComments.commented_by == user_id)
    )
    comments = result.scalars().all()
    return comments


# ----------------- Update comment -----------------
@router.put("/{comment_id}", response_model=CommentResponse, summary="Update comment text")
async def update_comment(
    comment_id: int,
    comment_update: CommentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    result = await db.execute(
        select(models.TicketComments)
        .options(
            selectinload(models.TicketComments.ticket_comment),
            selectinload(models.TicketComments.commented_user)
        )
        .where(models.TicketComments.id == comment_id)   # Fixed: .id
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No comment found")
    
    comment.comment = comment_update.comment
    try:
        await db.commit()
        await db.refresh(comment)
        return comment
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update comment")


# ----------------- Delete comment -----------------
@router.delete("/{comment_id}", status_code=status.HTTP_200_OK, summary="Delete comment")
async def delete_comment(comment_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    comment = await db.get(models.TicketComments, comment_id)  # Fixed: Clean primary key lookup
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No comment found")
    
    try:
        await db.delete(comment)
        await db.commit()
        return {"message": f"Deleted comment {comment_id} successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete comment")