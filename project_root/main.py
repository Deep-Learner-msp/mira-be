from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Path, Query
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, desc, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
import uuid
import asyncio
from typing import Optional, List
from datetime import datetime
import traceback
import uvicorn

app = FastAPI()

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./chatbot.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    session_id = Column(String, unique=True, index=True)

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("user_sessions.session_id"), index=True)
    message_type = Column(String)  # 'user' or 'bot'
    content = Column(Text)

    user_session = relationship("UserSession", back_populates="messages")

UserSession.messages = relationship("ChatMessage", order_by=ChatMessage.id, back_populates="user_session")

Base.metadata.create_all(bind=engine)

class UserQuestion(BaseModel):
    question: str
    session_id: Optional[str] = None

class SessionStatus(BaseModel):
    session_id: str

@app.post("/chat")
async def chat(user_question: UserQuestion, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        if user_question.session_id:
            # Check if the session exists
            existing_session = db.query(UserSession).filter(
                UserSession.session_id == user_question.session_id
            ).first()
            if not existing_session:
                raise HTTPException(status_code=404, detail="Session not found")
            session_id = user_question.session_id
        else:
            # Create a new session
            session_id = str(uuid.uuid4())
            new_session = UserSession(session_id=session_id)
            db.add(new_session)
            db.commit()

        background_tasks.add_task(process_chat, session_id, user_question.question)
        return {"message": "Chat request received", "session_id": session_id}
    except Exception as e:
        db.rollback()
        error_detail = f"An error occurred: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)

@app.post("/get_status")
async def get_status(session_status: SessionStatus, db: Session = Depends(get_db)):
    try:
        # Get the latest message for the given session_id
        latest_message = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_status.session_id
        ).order_by(desc(ChatMessage.id)).first()

        if not latest_message:
            raise HTTPException(status_code=404, detail="Session not found")

        # Count the number of messages in the session
        message_count = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_status.session_id
        ).count()

        # Check if the latest message is from the bot
        status = "completed" if latest_message.message_type == "bot" else "processing"
        loading = status != "completed"

        return {
            "status": status,
            "size": message_count,
            "loading": loading
        }
    except Exception as e:
        error_detail = f"An error occurred: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)

@app.get("/user_sessions/{user_id}")
async def get_user_sessions(user_id: str):
    db = SessionLocal()
    try:
        user_sessions = db.query(UserSession).filter(UserSession.user_id == user_id).all()
        return {"user_id": user_id, "session_ids": [session.session_id for session in user_sessions]}
    finally:
        db.close()

async def process_chat(session_id: str, question: str):
    db = SessionLocal()
    try:
        # Save user message
        user_message = ChatMessage(
            session_id=session_id,
            message_type="user",
            content=question
        )
        db.add(user_message)
        db.commit()

        # Add a delay of 15 seconds
        await asyncio.sleep(15)

        # Generate dummy response
        bot_response = "This is a dummy response from the chatbot."

        # Save bot message
        bot_message = ChatMessage(
            session_id=session_id,
            message_type="bot",
            content=bot_response
        )
        db.add(bot_message)
        db.commit()
    except Exception as e:
        db.rollback()
        # Log the error here
    finally:
        db.close()

class MessageResponse(BaseModel):
    content: str
    message_type: str

@app.get("/messages/{session_id}", response_model=List[MessageResponse])
async def get_messages(
    session_id: str = Path(..., description="Session ID to retrieve messages for"),
    limit: int = Query(50, description="Maximum number of messages to return"),
    db: Session = Depends(get_db)
):
    try:
        messages = db.query(ChatMessage).filter(  # Change Message to ChatMessage
            ChatMessage.session_id == session_id
        ).limit(limit).all()

        if not messages:
            raise HTTPException(status_code=404, detail="No messages found for this session")

        return [
            MessageResponse(
                content=msg.content,
                message_type=msg.message_type,  # Use the message_type from ChatMessage
            ) for msg in messages  # Reverse to get oldest messages first
        ]
    except Exception as e:
        error_detail = f"An error occurred: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=error_detail)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
