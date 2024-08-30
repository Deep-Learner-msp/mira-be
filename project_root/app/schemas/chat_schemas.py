from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserQuestion(BaseModel):
    question: str
    session_id: Optional[str] = None

class SessionStatus(BaseModel):
    session_id: str

class MessageResponse(BaseModel):
    content: str
    message_type: str
    timestamp: datetime

    class Config:
        orm_mode = True
