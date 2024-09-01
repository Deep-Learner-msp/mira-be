import os
import uuid
import asyncio
from dotenv import load_dotenv

from fastapi import HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_openai.chat_models import ChatOpenAI
import os
from getpass import getpass
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_openai.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import PromptTemplate

from models.chat_models import UserSession, ChatMessage, MemoryStore
from schemas.chat_schemas import UserQuestion, SessionStatus, MessageResponse
from prompts.mira_template import mira_template
from prompts.memory_template import memory_template

from typing import List
from models.chat_models import ChatMessage
# Load environment variables
load_dotenv()

def get_chat_history(db: Session, sessionId: str) -> str:
    messages: List[ChatMessage] = db.query(ChatMessage).filter(
        ChatMessage.sessionId == sessionId
    ).order_by(ChatMessage.id.desc()).limit(10).all()
    
    chat_history = ""
    for msg in reversed(messages):
        chat_history += f"{'Human' if msg.message_type == 'user' else 'AI'}: {msg.content}\n"
    return chat_history

async def create_session(user_question: UserQuestion, background_tasks: BackgroundTasks, db: Session):
    if user_question.sessionId:
        existing_session = db.query(UserSession).filter(UserSession.sessionId == user_question.sessionId).first()
        if not existing_session:
            raise HTTPException(status_code=404, detail="Session not found")
        sessionId = user_question.sessionId
    else:
        sessionId = str(uuid.uuid4())
        new_session = UserSession(sessionId=sessionId, session_name=user_question.question[:20])
        db.add(new_session)
        db.commit()

    background_tasks.add_task(process_chat, sessionId, user_question.question, db)
    return {"message": "Chat request received", "sessionId": sessionId}

async def get_session_status(session_status: SessionStatus, db: Session):
    latest_message = db.query(ChatMessage).filter(
        ChatMessage.sessionId == session_status.sessionId
    ).order_by(desc(ChatMessage.id)).first()

    if not latest_message:
        raise HTTPException(status_code=404, detail="Session not found")

    message_count = db.query(ChatMessage).filter(
        ChatMessage.sessionId == session_status.sessionId
    ).count()

    status = "Completed processing your question" if latest_message.message_type == "bot" else "Processing your question"
    loading = status != "Completed processing your question"

    return {
        "status_message": status,
        "size": message_count,
        "loading": loading
    }

async def get_user_sessions(user_id: str, db: Session):
    user_sessions = db.query(UserSession).filter(UserSession.user_id == user_id).all()
    return {"user_id": user_id, "sessionIds": [session.sessionId for session in user_sessions]}

from datetime import datetime, timezone

async def get_all_sessions(db: Session):
    user_sessions = db.query(UserSession).all()
    return {
        "generatedAt": user_sessions[0].created_at.isoformat() if user_sessions else datetime.now(timezone.utc).isoformat(),
        "sessions": [
            {
                "sessionId": session.sessionId,
                "label": session.session_name or f"Session {session.sessionId[:8]}",
                "lastModified": session.updated_at.isoformat() if session.updated_at else session.created_at.isoformat()
            }
            for session in user_sessions
        ]
    }

async def text_sql_generation(question: str, sessionId: str, db: Session):
    try:
        # Fetch or create memory for the session
        memory_store = db.query(MemoryStore).filter(MemoryStore.sessionId == sessionId).first()
        if not memory_store:
            memory_store = MemoryStore(sessionId=sessionId, memory="")
            db.add(memory_store)
            db.commit()

        llm = ChatOpenAI(model="gpt-4o",temperature=0.7, streaming=True)

        memory_prompt = PromptTemplate(
            input_variables=["chat_history", "input", "memory_store"], template=memory_template
        )
        memory_chain = LLMChain(
            llm=llm, prompt=memory_prompt, verbose=False
        )
        mira_prompt = PromptTemplate(
            input_variables=["chat_history", "input", "memory_store"], template=mira_template
        )
        history = get_chat_history(db, sessionId)
        mira_chain = LLMChain(
            llm=llm, prompt=mira_prompt, verbose=False
        )
        
        # Use the memory from the database
        updated_memory = memory_chain.predict(memory_store=memory_store.memory, input=question, chat_history=history)
        response = mira_chain.predict(input=question, memory_store=updated_memory, chat_history=history)

        # Update the memory in the database
        memory_store.memory = updated_memory
        db.commit()

        return response

    except Exception as e:
        db.rollback()
        print(f"Error in text generation: {str(e)}")
        return f"I apologize, but I encountered an error while processing your request. Could you please rephrase your question?"

async def process_chat(sessionId: str, question: str, db: Session):
    try:
        user_message = ChatMessage(sessionId=sessionId, message_type="user", content=question)
        db.add(user_message)
        db.commit()
        bot_response_future = asyncio.create_task(text_sql_generation(question, sessionId, db))

        # Wait for the bot response
        bot_response = await bot_response_future

        bot_message = ChatMessage(sessionId=sessionId, message_type="bot", content=bot_response)
        db.add(bot_message)
        db.commit()
    except Exception as e:
        db.rollback()
        # Log the error here
    finally:
        db.close()

async def get_messages(sessionId: str, startOffset: int, endOffset: int | None, db: Session):
    query = db.query(ChatMessage).filter(
        ChatMessage.sessionId == sessionId
    ).order_by(ChatMessage.id.asc())  # Add ORDER BY clause

    # Apply offset
    query = query.offset(startOffset)

    # Apply limit if endOffset is provided
    if endOffset is not None:
        limit = endOffset - startOffset + 1
        query = query.limit(limit)

    messages = query.all()

    if not messages:
        raise HTTPException(status_code=404, detail="No messages found for this session")

    return {
        "messages": [
            MessageResponse(
                messageId=msg.id,
                message=msg.content,
                profile=msg.message_type,  # Assuming message_type corresponds to profile
                time=msg.timestamp  # Assuming there's a timestamp field, adjust if needed
            ) for msg in messages
        ]
    }
