from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from supportops.database import get_db
from supportops.schemas import CategoryCreate, CategoryResponse, ReassignCategoryTickets
import supportops.models as models
from supportops.auth import CurrentUser, ManagerUser,AdminUser

router = APIRouter()


# ----------------- Create Category -----------------
@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED, summary="Create a new category")
async def create_category(
    category: CategoryCreate,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    new_category = models.Category(**category.model_dump())
    new_category.name = new_category.name.lower()
    try:
        db.add(new_category)
        await db.commit()
        await db.refresh(new_category)
        return new_category
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category with this name already exists",
        )
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create category",
        )


# ----------------- Get All Categories -----------------
@router.get("", response_model=list[CategoryResponse], summary="Get all categories")
async def get_all_categories(current_user:CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        result = await db.execute(select(models.Category).order_by(models.Category.id))
        return result.scalars().all()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred",
        )


# ----------------- Get Category By ID -----------------
@router.get("/{category_id}", response_model=CategoryResponse, summary="Get a category by ID")
async def get_category_by_id(
    category_id: int,
    current_user:CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    category = await db.get(models.Category, category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    return category


# ----------------- Update Category -----------------
@router.put("/{category_id}", response_model=CategoryResponse, summary="Update a category")
async def update_category(
    category_id: int,
    category_data: CategoryCreate,
    current_user:AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    existing_category = await db.get(models.Category, category_id)
    if not existing_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    for field, value in category_data.model_dump(exclude_unset=True).items():
        setattr(existing_category, field, value)

    existing_category.name = existing_category.name.lower()

    try:
        await db.commit()
        await db.refresh(existing_category)
        return existing_category
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another category with this name already exists",
        )
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update category",
        )


# ----------------- Delete Category -----------------
@router.delete("/{category_id}", summary="Delete a category")
async def delete_category(
    category_id: int,
    current_user:AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    existing_category = await db.get(models.Category, category_id)
    if not existing_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    try:
        await db.delete(existing_category)
        await db.commit()
        return {"message": f"Category {existing_category.name} deleted successfully"}
    except IntegrityError:
        # If tickets are linked to this category
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete category because it has tickets associated with it",
        )
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete category",
        )


#----------------- Update Category for tickets -------------------------
@router.put("/{category_id}/reassign-tickets", summary="Move all tickets from one category to another")
async def reassign_category_tickets(
    category_id: int,
    payload: ReassignCategoryTickets,
    current_user:AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # 1. Get old category 
    old_category = await db.get(models.Category, category_id)
    # 2. Check target category exists
    new_category = await db.get(models.Category, payload.new_category_id)
    if not new_category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target category not found")
    # 3. Perform a fast bulk SQL UPDATE
    try:
        update_stmt = (
            update(models.Ticket)
            .where(models.Ticket.category_id == category_id)
            .values(category_id=payload.new_category_id)
        )
        result = await db.execute(update_stmt)
        await db.commit()
        return {
            "message": f"Successfully moved {result.rowcount} tickets from '{old_category.name}' to '{new_category.name}'",
            "tickets_moved": result.rowcount,
            "source_category_id": category_id,
            "target_category_id": payload.new_category_id,
        }
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reassign category tickets",
        )