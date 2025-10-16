from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, text
from .db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, nullable=False)  # <-- было Integer
    username = Column(String(64))
    display_name = Column(String(128))
    subscribed = Column(Boolean, nullable=False, default=True)
    is_admin = Column(Boolean, nullable=False, default=False)
    accepted_terms = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=text("now()"))

class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, nullable=False)  # <-- было Integer
    username = Column(String(64))
    message = Column(String(4096), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("now()"))
