from email._header_value_parser import RouteComponentMarker
from fastapi import APIRouter, HTTPException, status, Depends
from supportops.schemas import (
    TicketCreate, TicketResponse, TicketAssignment, TicketResolution, 
    TicketUpdate, TicketStatusUpdate, TicketCommentsCreate, TicketCommentsResponse,
    TicketBasicResponse, TicketClosed
)
from supportops.database import get_db
from sqlalchemy.orm import Session, selectinload
from typing import Annotated
from sqlalchemy import select, func
import supportops.models as models
import uuid
from datetime import datetime, UTC

router = APIRouter()

#create ticket
@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED, name="create_ticket", summary="Create a new ticket")
def create_ticket(ticket: TicketCreate, db:Annotated[Session, Depends(get_db)]):
    new_ticket = models.Ticket(**ticket.model_dump())  ##** do unpacking each dictionary item to keyword = value and model_dump() conversts pydantic object to regular python dictionary
    #Adding the backend values to the ticket
    max_id = db.execute(select(models.Ticket.id).order_by(models.Ticket.id.desc()).limit(1)).scalar_one_or_none()
    if max_id is None:
        max_id = 1
    else:
        max_id = max_id + 1
    new_ticket.id = max_id
    new_ticket.ticket_number = "TKT"+str(uuid.uuid1().hex)[:16]
    new_ticket.created_at = datetime.now(UTC)
    new_ticket.updated_at = datetime.now(UTC)
    new_ticket.status = "New"
    
    try:
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
        return new_ticket
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    


#get all tickets
@router.get("", response_model=list[TicketResponse], name="get_all_tickets", summary="Get all tickets")
def get_all_tickets(db: Session = Depends(get_db)):
    try:
        results = db.execute(select(models.Ticket).order_by(models.Ticket.id))
        tickets = results.scalars().all()
        return tickets
    except Exception as e:
        raise HTTPException(status_code= status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



#get ticket by id
@router.get("/{id}", response_model=TicketResponse, name="get_ticket_by_id", summary="Get ticket by ID")
def get_ticket_by_id(id: int, db: Session = Depends(get_db)):
    try:
        result = db.execute(select(models.Ticket).filter(models.Ticket.id == id))
        ticket = result.scalar_one_or_none()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket



#update ticket
@router.patch("/{id}", response_model=TicketResponse, name="update_ticket", summary="Update ticket")
def update_ticket(id: int, ticket: TicketUpdate, db: Session = Depends(get_db)):
    try:
        result = db.execute(select(models.Ticket).where(models.Ticket.id == id))
        ticket_result = result.scalar_one_or_none()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if ticket_result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    update_data = ticket.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(ticket_result, key, value)  ## Another way of keyword mapping for databse insertion
    ticket_result.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(ticket_result, attribute_names=["category_id", "assignee_id", "requester_id"])
    return ticket_result
    
    

#Delete ticket
@router.delete("/{id}", name="delete_ticket", summary="Delete ticket")
def delete_ticket(id: int, db: Session = Depends(get_db)):
    try:
        result = db.execute(select(models.Ticket).filter(models.Ticket.id == id))
        ticket = result.scalar_one_or_none()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    #Delete the related comments in the db
    try:
        result = db.execute(select(models.TicketComments).where(models.TicketComments.ticket_id == id))
        comments = result.scalars().all()
        for comment in comments:
            db.delete(comment)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    db.delete(ticket)
    db.commit()
    return {"message": f"Ticket {ticket.ticket_number} deleted successfully"}

#Ticket Assignemnet
@router.post("/{id}/assign", response_model=TicketBasicResponse, name="assign_ticket", summary="Assign ticket to user")
def assign_ticket(id: int, ticket: TicketAssignment, db: Session = Depends(get_db)):
    try:
        result = db.execute(select(models.Ticket).where(models.Ticket.id == id))
        ticket_result = result.scalar_one_or_none()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if ticket_result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    update_data = ticket.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(ticket_result, key, value)
    ticket_result.updated_at = datetime.now(UTC)
    ticket_result.status = "Assigned"
    db.commit()
    db.refresh(ticket_result, attribute_names=["category_id", "assignee_id", "requester_id"])
    return ticket_result


#ticket resolution
@router.post("/{id}/resolve", response_model=TicketBasicResponse, name="resolve_ticket", summary="Resolve ticket")
def resolve_ticket(id: int, ticket: TicketResolution, db: Session = Depends(get_db)):
    try:
        result = db.execute(select(models.Ticket).where(models.Ticket.id == id))
        ticket_result = result.scalar_one_or_none()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    if ticket_result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if ticket.resolution is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resolution is required")
    ticket_result.resolution = ticket.resolution
    ticket_result.status = "Resolved"
    ticket_result.resolved_at = datetime.now(UTC)
    db.commit()
    db.refresh(ticket_result, attribute_names=["category_id", "assignee_id", "requester_id"])
    return ticket_result

 #Ticket closure with comment
@router.post("/{id}/close", response_model=TicketBasicResponse, name="close_ticket", summary="Close ticket")
def close_ticket(id: int, ticket: TicketClosed, db: Session = Depends(get_db)):
    try:
        result = db.execute(select(models.Ticket).where(models.Ticket.id == id))
        ticket_result = result.scalar_one_or_none()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    if ticket_result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if ticket.comment is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment is required")

    #Adding the comment to the ticket
    comment=TicketCommentsCreate(
        comment=ticket.comment,
        commented_by=ticket_result.requester_id
    )
    add_ticket_comment(id, comment, db)
    
    ticket_result.status = "Closed"
    ticket_result.closed_at = datetime.now(UTC)
    
    db.commit()
    db.refresh(ticket_result, attribute_names=["category_id", "assignee_id", "requester_id"])
    return ticket_result



#Ticket status update
@router.post("/{id}/status", response_model=TicketBasicResponse, name="status_update", summary="Update ticket status")
def status_update(id: int, ticket: TicketStatusUpdate, db: Session = Depends(get_db)):
    try:
        result = db.execute(select(models.Ticket).where(models.Ticket.id == id))
        ticket_result = result.scalar_one_or_none()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    if ticket_result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if ticket.status not in ["New", "Assigned", "Resolved", "Closed"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
    if ticket.status == "Resolved":
        ticket_result.status = ticket.status
        ticket_result.resolution = ticket.resolution
        ticket_result.resolved_at = datetime.now(UTC)
    elif ticket.status == "Closed":
        ticket_result.status = ticket.status
        new_comment = TicketCommentsCreate(
            comment="Ticket has been closed",
            commented_by=ticket_result.assignee_id,
        )
        add_ticket_comment(id, new_comment, db)
        ticket_result.closed_at = datetime.now(UTC)
    ticket_result.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(ticket_result, attribute_names=["category_id", "assignee_id", "requester_id"])
    return ticket_result


#Ticket comments
@router.post("/{id}/comments", response_model=TicketCommentsResponse, name="add_comment", summary="Add comment to ticket")
def add_comment(id: int, comment: TicketCommentsCreate, db: Annotated[Session, Depends(get_db)]):
    try:
        result = db.execute(select(models.Ticket).where(models.Ticket.id == id))
        ticket_result = result.scalar_one_or_none()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    if ticket_result is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if comment.comment is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment is required")
    if comment.commented_by is None:
        comment.commented_by = ticket_result.requester_id
    new_comment = add_ticket_comment(id, comment, db)
    return new_comment



#Helper functions
def add_ticket_comment(ticket_id, comment:TicketCommentsCreate, db):
    try:
        max_comment_id = db.execute(func.max(models.TicketComments.id)).scalar_one_or_none()
        new_comment = models.TicketComments(
            id=max_comment_id + 1 if max_comment_id is not None else 1,
            ticket_id = ticket_id,
            comment=comment.comment,
            commented_by=comment.commented_by,
            date_time=datetime.now(UTC),
        )
        db.add(new_comment)
        db.commit()
        db.refresh(new_comment)
        return new_comment
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
        