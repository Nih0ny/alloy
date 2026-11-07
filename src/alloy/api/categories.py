from typing import List
from fastapi import APIRouter, Depends, status

from alloy.models.category_schemas import (
    CategoryCreateUpdate,
    CategoryPublicResponse,
    CategoryAdminResponse,
    CategoryDeleteResponse,
)
from alloy.services.category_service import CategoryService
from alloy.dependencies import get_current_user, get_category_service

router = APIRouter(prefix="/api/v1/categories", tags=["Categories"])


@router.get("", response_model=List[CategoryPublicResponse])
async def list_public_categories(
    category_service: CategoryService = Depends(get_category_service)
):
    return await category_service.get_public_categories()


@router.get("/admin", response_model=List[CategoryAdminResponse])
async def list_categories_for_admin(
    current_user: dict = Depends(get_current_user),
    category_service: CategoryService = Depends(get_category_service)
):
    return await category_service.get_all_categories_for_admin(current_user)


@router.post("", response_model=CategoryAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    cat_in: CategoryCreateUpdate,
    current_user: dict = Depends(get_current_user),
    category_service: CategoryService = Depends(get_category_service)
):
    return await category_service.create_category(cat_in, current_user)


@router.put("/{category_id}", response_model=CategoryAdminResponse)
async def update_category(
    category_id: str,
    cat_in: CategoryCreateUpdate,
    current_user: dict = Depends(get_current_user),
    category_service: CategoryService = Depends(get_category_service)
):
    return await category_service.update_category(category_id, cat_in, current_user)


@router.delete("/{category_id}", response_model=CategoryDeleteResponse)
async def delete_category(
    category_id: str,
    current_user: dict = Depends(get_current_user),
    category_service: CategoryService = Depends(get_category_service)
):
    return await category_service.delete_or_archive_category(category_id, current_user)
