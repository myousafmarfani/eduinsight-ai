from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, valid_student_id
from app.chatbot.chat_service import ChatService
from app.schemas.chatbot import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


def get_chat_service() -> ChatService:
    return ChatService()


@router.post("/students/{student_id}/chat/", response_model=ChatResponse)
def chat(request: ChatRequest, student_id: str = Depends(valid_student_id), db: Session = Depends(get_db),
         service: ChatService = Depends(get_chat_service)) -> ChatResponse:
    """Answer a question about this student's results (history is kept per student and session)."""
    return service.reply(db, student_id, request.message, request.session_id)
