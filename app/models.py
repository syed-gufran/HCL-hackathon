from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


# 👤 USERS
class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    email = Column(String(150), unique=True, index=True)
    password_hash = Column(String(255))
    role = Column(String(20))  # 'user' or 'admin'
    department = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tickets = relationship("Ticket", back_populates="user")
    resolutions = relationship("Resolution", back_populates="admin")


# 🏷 CATEGORIES
class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True)
    description = Column(Text)

    tickets = relationship("Ticket", back_populates="category")


# 📋 TICKETS
class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    category_id = Column(Integer, ForeignKey("categories.category_id"))

    title = Column(String(200))
    description = Column(Text, nullable=False)

    priority = Column(String(20))  # low, med, high
    status = Column(String(30), default="open")

    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow)
    resolved_date = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="tickets")
    category = relationship("Category", back_populates="tickets")
    resolutions = relationship("Resolution", back_populates="ticket")
    status_logs = relationship("TicketStatusLog", back_populates="ticket")


# ✅ RESOLUTIONS
class Resolution(Base):
    __tablename__ = "resolutions"

    resolution_id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.ticket_id"))
    added_by = Column(Integer, ForeignKey("users.user_id"))

    resolution_text = Column(Text, nullable=False)
    resolved_date = Column(DateTime, default=datetime.utcnow)
    helpful_count = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)

    # Relationships
    ticket = relationship("Ticket", back_populates="resolutions")
    admin = relationship("User", back_populates="resolutions")


# 📜 TICKET STATUS LOG
class TicketStatusLog(Base):
    __tablename__ = "ticket_status_log"

    log_id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.ticket_id"))
    changed_by = Column(Integer, ForeignKey("users.user_id"))

    old_status = Column(String(30))
    new_status = Column(String(30))
    changed_at = Column(DateTime, default=datetime.utcnow)
    note = Column(Text, nullable=True)

    # Relationships
    ticket = relationship("Ticket", back_populates="status_logs")