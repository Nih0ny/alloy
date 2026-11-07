from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from alloy.models.complaint_schemas import (
    ComplaintCreate,
    ComplaintRejectRequest,
    UserBlockRequest,
    ComplaintResponse,
    AdminUserRegistryItem,
)
from alloy.services.complaint_service import ComplaintService
from alloy.dependencies import get_current_user, get_complaint_service

router = APIRouter(prefix="/api/v1", tags=["Complaints & User Moderation"])

@router.post(
    "/complaints",
    response_model=ComplaintResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_complaint(
    complaint_in: ComplaintCreate,
    current_user: dict = Depends(get_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service)
):
    return await complaint_service.submit_complaint(complaint_in, current_user)

@router.get("/admin/complaints", response_model=List[ComplaintResponse])
async def list_complaints_for_admin(
    status_filter: Optional[str] = Query(
        None,
        description="Filter by status: 'Pending', 'Rejected', 'Resolved'"
    ),
    current_user: dict = Depends(get_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service)
):
    return await complaint_service.get_complaints_for_admin(current_user, status_filter)

@router.get("/admin/complaints/{complaint_id}", response_model=ComplaintResponse)
async def get_complaint_details(
    complaint_id: str,
    current_user: dict = Depends(get_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service)
):
    return await complaint_service.get_complaint_details_for_admin(complaint_id, current_user)

@router.patch("/admin/complaints/{complaint_id}/reject", response_model=ComplaintResponse)
async def reject_complaint(
    complaint_id: str,
    reject_in: ComplaintRejectRequest,
    current_user: dict = Depends(get_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service)
):
    return await complaint_service.reject_complaint(complaint_id, reject_in, current_user)

@router.post("/admin/complaints/{complaint_id}/delete-content", response_model=ComplaintResponse)
async def delete_reported_content(
    complaint_id: str,
    current_user: dict = Depends(get_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service)
):
    return await complaint_service.delete_reported_content_and_resolve(complaint_id, current_user)

@router.get("/admin/users", response_model=List[AdminUserRegistryItem])
async def list_users_registry(
    role: Optional[str] = Query(None, description="Filter by role: 'Volunteer' or 'Organizer'"),
    account_status: Optional[str] = Query(None, description="Filter by status: 'Active' or 'Blocked'"),
    current_user: dict = Depends(get_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service)
):
    return await complaint_service.get_users_registry(current_user, role, account_status)

@router.patch("/admin/users/{user_id}/block", response_model=AdminUserRegistryItem)
async def block_user_account(
    user_id: str,
    block_in: UserBlockRequest,
    current_user: dict = Depends(get_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service)
):
    return await complaint_service.block_user(user_id, block_in, current_user)

@router.patch("/admin/users/{user_id}/unblock", response_model=AdminUserRegistryItem)
async def unblock_user_account(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    complaint_service: ComplaintService = Depends(get_complaint_service)
):
    return await complaint_service.unblock_user(user_id, current_user)
