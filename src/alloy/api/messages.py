from typing import List
from fastapi import APIRouter, Depends, Query, status

from alloy.models.communication_schemas import (
    DirectMessageCreate,
    DirectMessageResponse,
    ConversationSummaryResponse,
)
from alloy.services.communication_service import MessageService
from alloy.dependencies import get_current_user, get_message_service

router = APIRouter(prefix="/api/v1/messages", tags=["Messages"])


@router.post("", response_model=DirectMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_direct_message(
    msg_in: DirectMessageCreate,
    current_user: dict = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service)
):
    return await message_service.send_message(msg_in, current_user)


@router.get("/conversations", response_model=List[ConversationSummaryResponse])
async def list_my_conversations(
    current_user: dict = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service)
):
    return await message_service.get_my_conversations(current_user)


@router.get("/conversations/{interlocutor_id}", response_model=List[DirectMessageResponse])
async def get_conversation_history(
    interlocutor_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service)
):
    return await message_service.get_conversation(interlocutor_id, current_user, skip, limit)
