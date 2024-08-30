from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

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

class MemoryStore(Base):
    __tablename__ = "memory_store"

    session_id = Column(String, primary_key=True, index=True)
    memory = Column(Text, default="")
