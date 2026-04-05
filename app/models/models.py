from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Boolean, func
from app.database.database import Base


class SujasSummary(Base):
    __tablename__ = "sujas_summaries"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content_html = Column(Text, nullable=False)
    pdf_file = Column(String(500), nullable=True)
    date = Column(Date, nullable=False, index=True)
    month = Column(String(20), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EconomicsChapter(Base):
    __tablename__ = "economics_chapters"

    id = Column(Integer, primary_key=True, index=True)
    chapter_no = Column(Integer, nullable=False, default=0)
    chapter_name = Column(String(255), nullable=False)
    chapter_name_hindi = Column(String(255), nullable=True)
    topic = Column(String(500), nullable=False, default='')
    content_html = Column(Text, nullable=False)
    youtube_url = Column(String(500), nullable=True)
    is_live = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
