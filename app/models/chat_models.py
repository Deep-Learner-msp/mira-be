from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, DateTime, VARCHAR
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(VARCHAR(36), index=True)
    sessionId = Column(VARCHAR(36), unique=True, index=True)
    session_name = Column(VARCHAR(36), default="Unnamed Session")
    is_valid = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    sessionId = Column(VARCHAR(36), ForeignKey("user_sessions.sessionId"), index=True)
    message_type = Column(VARCHAR(36))  # 'user' or 'bot'
    content = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_session = relationship("UserSession", back_populates="messages")

UserSession.messages = relationship("ChatMessage", order_by=ChatMessage.id, back_populates="user_session")

class MemoryStore(Base):
    __tablename__ = "memory_store"

    sessionId = Column(VARCHAR(36), primary_key=True, index=True)
    memory = Column(Text, default="")
