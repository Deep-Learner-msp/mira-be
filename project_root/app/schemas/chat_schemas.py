from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserQuestion(BaseModel):
    question: str
    sessionId: Optional[str] = None

class SessionStatus(BaseModel):
    sessionId: str

class MessageResponse(BaseModel):
    messageId: int
    message: str
    profile: str
    time: datetime

class MessageRequest(BaseModel):
    sessionId: str
    startOffset: int
    endOffset: int
