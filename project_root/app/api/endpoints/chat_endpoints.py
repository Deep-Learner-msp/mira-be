from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Path, Query
from sqlalchemy.orm import Session
from database import get_db
from schemas.chat_schemas import UserQuestion, SessionStatus, MessageResponse, MessageRequest
from services.chat_services import create_session, get_session_status, get_user_sessions, get_all_sessions, get_messages
from typing import List, Dict, Any

router = APIRouter()

def create_response(success: bool, result: Any = None, error: str = None) -> Dict[str, Any]:
    return {
        "success": success,
        "error": {"message": error} if error else {},
        "result": result if result is not None else {}
    }

@router.post("/process_question")
async def chat(user_question: UserQuestion, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        result = await create_session(user_question, background_tasks, db)
        return create_response(True, result)
    except Exception as e:
        return create_response(False, error=str(e))

@router.post("/create_session")
async def session(user_question: UserQuestion, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        result = await create_session(user_question, background_tasks, db)
        return create_response(True, result)
    except Exception as e:
        return create_response(False, error=str(e))

@router.post("/get_session_status")
async def session_status(session_status: SessionStatus, db: Session = Depends(get_db)):
    try:
        result = await get_session_status(session_status, db)
        return create_response(True, result)
    except Exception as e:
        return create_response(False, error=str(e))

@router.post("/user_sessions/{user_id}")
async def user_sessions(user_id: str, db: Session = Depends(get_db)):
    try:
        result = await get_user_sessions(user_id, db)
        return create_response(True, result)
    except Exception as e:
        return create_response(False, error=str(e))

@router.post("/get_all_sessions")
async def all_sessions(db: Session = Depends(get_db)):
    try:
        result = await get_all_sessions(db)
        return create_response(True, result)
    except Exception as e:
        return create_response(False, error=str(e))

@router.post("/get_messages")
async def messages(
    message_request: MessageRequest,
    db: Session = Depends(get_db)
):
    try:
        result = await get_messages(message_request.sessionId, message_request.startOffset, message_request.endOffset, db)
        return create_response(True, result)
    except Exception as e:
        return create_response(False, error=str(e))

