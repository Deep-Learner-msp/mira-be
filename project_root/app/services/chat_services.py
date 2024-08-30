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

def get_chat_history(db: Session, session_id: str) -> str:
    messages: List[ChatMessage] = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).all()
    
    chat_history = ""
    for msg in messages:
        chat_history += f"{'Human' if msg.message_type == 'user' else 'AI'}: {msg.content}\n"
    return chat_history

async def create_session(user_question: UserQuestion, background_tasks: BackgroundTasks, db: Session):
    if user_question.session_id:
        existing_session = db.query(UserSession).filter(UserSession.session_id == user_question.session_id).first()
        if not existing_session:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = user_question.session_id
    else:
        session_id = str(uuid.uuid4())
        new_session = UserSession(session_id=session_id)
        db.add(new_session)
        db.commit()

    background_tasks.add_task(process_chat, session_id, user_question.question, db)
    return {"message": "Chat request received", "session_id": session_id}

async def get_session_status(session_status: SessionStatus, db: Session):
    latest_message = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_status.session_id
    ).order_by(desc(ChatMessage.id)).first()

    if not latest_message:
        raise HTTPException(status_code=404, detail="Session not found")

    message_count = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_status.session_id
    ).count()

    status = "completed" if latest_message.message_type == "bot" else "processing"
    loading = status != "completed"

    return {
        "status": status,
        "size": message_count,
        "loading": loading
    }

async def get_user_sessions(user_id: str, db: Session):
    user_sessions = db.query(UserSession).filter(UserSession.user_id == user_id).all()
    return {"user_id": user_id, "session_ids": [session.session_id for session in user_sessions]}

async def get_all_sessions(db: Session):
    user_sessions = db.query(UserSession).all()
    return {"session_ids": [session.session_id for session in user_sessions]}

async def text_sql_generation(question: str, session_id: str, db: Session):
    try:
        # Fetch or create memory for the session
        memory_store = db.query(MemoryStore).filter(MemoryStore.session_id == session_id).first()
        if not memory_store:
            memory_store = MemoryStore(session_id=session_id, memory="")
            db.add(memory_store)
            db.commit()

        llm = ChatOpenAI(model="gpt-4o",temperature=0.7, streaming=True)

        memory_prompt = PromptTemplate(
            input_variables=["chat_history", "input", "memory_store"], template=memory_template
        )
        memory_chain = LLMChain(
            llm=llm, prompt=memory_prompt, verbose=True
        )
        mira_prompt = PromptTemplate(
            input_variables=["chat_history", "input", "memory_store"], template=mira_template
        )
        history = get_chat_history(db, session_id)
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

async def process_chat(session_id: str, question: str, db: Session):
    try:
        user_message = ChatMessage(session_id=session_id, message_type="user", content=question)
        db.add(user_message)
        db.commit()
        bot_response_future = asyncio.create_task(text_sql_generation(question, session_id, db))

        # Wait for the bot response
        bot_response = await bot_response_future

        bot_message = ChatMessage(session_id=session_id, message_type="bot", content=bot_response)
        db.add(bot_message)
        db.commit()
    except Exception as e:
        db.rollback()
        # Log the error here
    finally:
        db.close()

async def get_messages(session_id: str, limit: int, db: Session):
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(desc(ChatMessage.id)).limit(limit).all()

    if not messages:
        raise HTTPException(status_code=404, detail="No messages found for this session")

    return [
        MessageResponse(
            content=msg.content,
            message_type=msg.message_type,
            timestamp=msg.id  # Assuming id is used as a timestamp, adjust if needed
        ) for msg in reversed(messages)
    ]
