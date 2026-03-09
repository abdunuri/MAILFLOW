"""SQLAlchemy database models for MailFlow."""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

import config


class Base(DeclarativeBase):
    pass


class Category(Base):
    """User-defined email category with matching rules."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, default="")
    color = Column(String(20), default="#6366f1")  # hex colour for the UI badge
    # Comma-separated matching rules stored as JSON-encoded string
    sender_keywords = Column(Text, default="")   # match against From: header
    subject_keywords = Column(Text, default="")  # match against Subject:
    body_keywords = Column(Text, default="")     # match against email body
    priority = Column(Integer, default=0)        # higher = evaluated first
    use_ai_reply = Column(Boolean, default=False)  # AI generates reply when no template
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    emails = relationship(
        "Email",
        back_populates="category",
        # No cascade: when a category is deleted SQLAlchemy will set
        # category_id to NULL on the related email rows (nullable FK).
    )
    reply_templates = relationship(
        "ReplyTemplate", back_populates="category", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "sender_keywords": self.sender_keywords,
            "subject_keywords": self.subject_keywords,
            "body_keywords": self.body_keywords,
            "priority": self.priority,
            "use_ai_reply": self.use_ai_reply,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ReplyTemplate(Base):
    """Pre-specified auto-reply template linked to a category."""

    __tablename__ = "reply_templates"

    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name = Column(String(100), nullable=False)
    subject_prefix = Column(String(200), default="Re: ")
    body = Column(Text, nullable=False)
    auto_reply = Column(Boolean, default=False)  # send automatically?
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    category = relationship("Category", back_populates="reply_templates")

    def to_dict(self):
        return {
            "id": self.id,
            "category_id": self.category_id,
            "name": self.name,
            "subject_prefix": self.subject_prefix,
            "body": self.body,
            "auto_reply": self.auto_reply,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Email(Base):
    """Cached email record with categorisation result."""

    __tablename__ = "emails"

    id = Column(Integer, primary_key=True)
    gmail_id = Column(String(200), unique=True, nullable=False)
    thread_id = Column(String(200))
    subject = Column(Text, default="")
    sender = Column(Text, default="")
    recipient = Column(Text, default="")
    snippet = Column(Text, default="")
    body = Column(Text, default="")
    date = Column(DateTime)
    is_read = Column(Boolean, default=False)
    is_replied = Column(Boolean, default=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    category = relationship("Category", back_populates="emails")

    def to_dict(self):
        return {
            "id": self.id,
            "gmail_id": self.gmail_id,
            "thread_id": self.thread_id,
            "subject": self.subject,
            "sender": self.sender,
            "recipient": self.recipient,
            "snippet": self.snippet,
            "body": self.body,
            "date": self.date.isoformat() if self.date else None,
            "is_read": self.is_read,
            "is_replied": self.is_replied,
            "category_id": self.category_id,
            "category_name": self.category.name if self.category else None,
            "category_color": self.category.color if self.category else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

_engine = None
_Session = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            config.DATABASE_URL,
            connect_args={"check_same_thread": False}
            if "sqlite" in config.DATABASE_URL
            else {},
        )
    return _engine


def get_session():
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=get_engine())
    return _Session()


def _migrate_add_use_ai_reply():
    """Add use_ai_reply column to categories if it doesn't exist."""
    engine = get_engine()
    if "sqlite" not in config.DATABASE_URL:
        return
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE categories ADD COLUMN use_ai_reply BOOLEAN DEFAULT 0"
            ))
            conn.commit()
        except Exception:
            conn.rollback()
            # Column likely already exists
            pass


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(get_engine())
    _migrate_add_use_ai_reply()
