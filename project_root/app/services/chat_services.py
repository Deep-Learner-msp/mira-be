import os
import uuid
import asyncio
from dotenv import load_dotenv

from fastapi import HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai.chat_models import ChatOpenAI
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.schema import StrOutputParser

from models.chat_models import UserSession, ChatMessage
from schemas.chat_schemas import UserQuestion, SessionStatus, MessageResponse
from prompts.mira_template import mira_template

# Load environment variables
load_dotenv()

store = {}

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

def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

async def text_sql_generation(question: str, session_id: str):
    try:
        model = ChatOpenAI(streaming=True)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", mira_template),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
            ]
        )
        runnable = prompt | model | StrOutputParser()

        # Wrap the runnable with history management
        with_message_history = RunnableWithMessageHistory(
            runnable,
            get_session_history,
            input_messages_key="question",
            history_messages_key="history",
        )
        # Generate a response using the LangChain setup
        response = await asyncio.to_thread(
            with_message_history.invoke,
            {"question": question},
            {"configurable": {"session_id": session_id}}
        )
        return response
    except Exception as e:
        # Log the error and return a fallback response
        print(f"Error in text generation: {str(e)}")
        return f"I apologize, but I encountered an error while processing your request. Could you please rephrase your question?"

async def process_chat(session_id: str, question: str, db: Session):
    try:
        user_message = ChatMessage(session_id=session_id, message_type="user", content=question)
        db.add(user_message)
        db.commit()
        bot_response_future = asyncio.create_task(text_sql_generation(question, session_id))

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
