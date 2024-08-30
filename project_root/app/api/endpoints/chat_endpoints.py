from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Path, Query
from sqlalchemy.orm import Session
from database import get_db
from schemas.chat_schemas import UserQuestion, SessionStatus, MessageResponse
from services.chat_services import create_session, get_session_status, get_user_sessions, get_all_sessions, get_messages
from typing import List

router = APIRouter()

@router.post("/chat")
async def chat(user_question: UserQuestion, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    return await create_session(user_question, background_tasks, db)

@router.post("/get_status")
async def get_status(session_status: SessionStatus, db: Session = Depends(get_db)):
    return await get_session_status(session_status, db)

@router.get("/user_sessions/{user_id}")
async def user_sessions(user_id: str, db: Session = Depends(get_db)):
    return await get_user_sessions(user_id, db)

@router.get("/all_sessions")
async def all_sessions(db: Session = Depends(get_db)):
    return await get_all_sessions(db)

@router.get("/messages/{session_id}", response_model=List[MessageResponse])
async def messages(
    session_id: str = Path(..., description="Session ID to retrieve messages for"),
    limit: int = Query(50, description="Maximum number of messages to return"),
    db: Session = Depends(get_db)
):
    return await get_messages(session_id, limit, db)

