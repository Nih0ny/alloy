from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from alloy.models.communication_schemas import (
    SupportTicketCreate,
    SupportTicketUpdateStatus,
    SupportTicketResponse,
)
from alloy.services.communication_service import SupportService
from alloy.dependencies import (
    get_current_user,
    get_optional_current_user,
    get_support_service,
)

router = APIRouter(prefix="/api/v1/support", tags=["Support"])


@router.post("", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
async def submit_support_ticket(
    ticket_in: SupportTicketCreate,
    current_user: Optional[dict] = Depends(get_optional_current_user),
    support_service: SupportService = Depends(get_support_service)
):
    return await support_service.create_support_ticket(ticket_in, current_user)


@router.get("/my", response_model=List[SupportTicketResponse])
async def get_my_support_tickets(
    current_user: dict = Depends(get_current_user),
    support_service: SupportService = Depends(get_support_service)
):
    return await support_service.get_my_tickets(current_user)


@router.get("/admin", response_model=List[SupportTicketResponse])
async def list_all_tickets_for_admin(
    status_filter: Optional[str] = Query(None, description="Filter by status: New, In Progress, Resolved"),
    current_user: dict = Depends(get_current_user),
    support_service: SupportService = Depends(get_support_service)
):
    return await support_service.get_all_tickets_for_admin(current_user, status_filter)


@router.patch("/admin/{ticket_id}", response_model=SupportTicketResponse)
async def reply_and_update_support_ticket(
    ticket_id: str,
    update_in: SupportTicketUpdateStatus,
    current_user: dict = Depends(get_current_user),
    support_service: SupportService = Depends(get_support_service)
):
    return await support_service.update_ticket_by_admin(ticket_id, update_in, current_user)
