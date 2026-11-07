from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from supportops.database import get_db
from supportops.schemas import CategoryCreate, CategoryResponse
from typing import List
from supportops.models import Category


router = APIRouter(prefix="/v1/category", tags=["Category"])


# Create a new category
@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    category: CategoryCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """Create a new category"""
    try:
        new_category = Category(**category.dict())
        db.add(new_category)
        db.commit()
        db.refresh(new_category)
        return new_category
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

# Get all categories
@router.get("", response_model=List[CategoryResponse])
def get_all_categories(db: Annotated[Session, Depends(get_db)]):
    """Get all categories"""
    try:
        return db.execute(select(Category).order_by(Category.created_at.desc())).scalars().all()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

#catagoy update
@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    category: CategoryCreate,
    db: Annotated[Session, Depends(get_db)],
):
    """Update a category"""
    try:
        existing_category = db.execute(select(Category).where(Category.id == category_id)).scalar_one_or_none()
        if not existing_category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )
        for field, value in category.dict().items():
            setattr(existing_category, field, value)
        db.commit()
        db.refresh(existing_category)
        return existing_category
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

#catagoy delete
@router.delete("/{category_id}", response_model=CategoryResponse)
def delete_category(
    category_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Delete a category"""
    try:
        existing_category = db.execute(select(Category).where(Category.id == category_id)).scalar_one_or_none()
        if not existing_category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )
        db.delete(existing_category)
        db.commit()
        return existing_category
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

# catagoy by id
def get_category_by_id(
    category_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Get a category by ID"""
    try:
        existing_category = db.execute(select(Category).where(Category.id == category_id)).scalar_one_or_none()
        if not existing_category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found",
            )
        return existing_category
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )