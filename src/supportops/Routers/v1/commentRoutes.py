from sqlalchemy.engine import result
from fastapi import APIRouter, HTTPException, status, Depends

from supportops.schemas import CommentResponse
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func
from typing import Annotated
from supportops.database import get_db
import supportops.models as models

router = APIRouter()

@router.get("" , response_model=list[CommentResponse])
def get_comments(ticket_id : int , db:Annotated[Session, Depends(get_db)]):
    try:
        result = db.execute(select(models.TicketComments)
                            .options(selectinload(models.TicketComments.ticket_comment))
                            .options(selectinload(models.TicketComments.commented_user))
                            .where(models.TicketComments.ticket_id == ticket_id)).scalars().all()
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND , detail="No comments found")
        
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR , detail=str(e))


@router.get("/{comment_id}", response_model=CommentResponse)
def get_comment(comment_id : int , db:Annotated[Session, Depends(get_db)]):
    try:
        result = db.execute(select(models.TicketComments)
                            .options(selectinload(models.TicketComments.ticket_comment))
                            .options(selectinload(models.TicketComments.commented_user))
                            .where(models.TicketComments.comment_id == comment_id)).scalar_one_or_none()
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND , detail="No comment found")
        
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR , detail=str(e))

#user comments
@router.get("/user/{user_id}", response_model=list[CommentResponse])
def get_user_comments(user_id : int , db:Annotated[Session, Depends(get_db)]):
    try:
        result = db.execute(select(models.TicketComments)
                            .options(selectinload(models.TicketComments.ticket_comment))
                            .options(selectinload(models.TicketComments.commented_user))
                            .where(models.TicketComments.user_id == user_id)).scalars().all()
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND , detail="No comments found")
        
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR , detail=str(e))