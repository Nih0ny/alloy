from typing import List
from fastapi import APIRouter, Depends, Query, status

from alloy.models.communication_schemas import CommentCreate, CommentResponse
from alloy.services.communication_service import CommentService
from alloy.dependencies import get_current_user, get_verified_user, get_comment_service

router = APIRouter(prefix="/api/v1", tags=["Comments"])


@router.get("/events/{event_id}/comments", response_model=List[CommentResponse])
async def list_event_comments(
    event_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    comment_service: CommentService = Depends(get_comment_service)
):
    return await comment_service.get_event_comments(event_id, skip, limit)


@router.post(
    "/events/{event_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_event_comment(
    event_id: str,
    comment_in: CommentCreate,
    current_user: dict = Depends(get_verified_user),
    comment_service: CommentService = Depends(get_comment_service)
):
    return await comment_service.add_comment(event_id, comment_in, current_user)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: str,
    current_user: dict = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service)
):
    await comment_service.delete_comment(comment_id, current_user)
