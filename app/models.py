import json
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base


class Platform(Base):
    __tablename__ = "platforms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    priority = Column(Integer, default=99)
    is_active = Column(Boolean, default=True)

    profiles = relationship("KOLProfile", back_populates="platform")


class KOL(Base):
    __tablename__ = "kols"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    name_zh = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    website = Column(String, nullable=True)
    region = Column(String, default="unknown")
    language = Column(String, default="mixed")
    bio_summary = Column(Text, nullable=True)
    total_score = Column(Float, default=0.0)
    tier = Column(String, default="D")
    status = Column(String, default="discovered")
    tags = Column(Text, nullable=True)  # JSON array
    competitor_history = Column(Text, nullable=True)  # JSON array
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_scanned_at = Column(DateTime, nullable=True)

    profiles = relationship("KOLProfile", back_populates="kol", cascade="all, delete-orphan")
    outreach_emails = relationship("OutreachEmail", back_populates="kol")

    @property
    def tags_list(self):
        if self.tags:
            return json.loads(self.tags)
        return []

    @tags_list.setter
    def tags_list(self, value):
        self.tags = json.dumps(value, ensure_ascii=False)

    @property
    def competitor_history_list(self):
        if self.competitor_history:
            return json.loads(self.competitor_history)
        return []

    @property
    def primary_profile(self):
        if self.profiles:
            return max(self.profiles, key=lambda p: p.follower_count or 0)
        return None

    @property
    def total_followers(self):
        return sum(p.follower_count or 0 for p in self.profiles)


class KOLProfile(Base):
    __tablename__ = "kol_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    kol_id = Column(Integer, ForeignKey("kols.id"), nullable=False)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=False)
    platform_username = Column(String, nullable=True)
    profile_url = Column(String, nullable=True)
    follower_count = Column(Integer, nullable=True)
    following_count = Column(Integer, nullable=True)
    post_count = Column(Integer, nullable=True)
    avg_likes = Column(Float, nullable=True)
    avg_comments = Column(Float, nullable=True)
    avg_shares = Column(Float, nullable=True)
    engagement_rate = Column(Float, nullable=True)
    subscriber_count = Column(Integer, nullable=True)
    avg_views = Column(Integer, nullable=True)
    bio_text = Column(Text, nullable=True)
    is_verified = Column(Boolean, default=False)
    content_relevance_score = Column(Float, default=0.0)
    last_post_date = Column(DateTime, nullable=True)
    raw_data = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    kol = relationship("KOL", back_populates="profiles")
    platform = relationship("Platform", back_populates="profiles")


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String, nullable=False)  # full_discovery / platform_scan / kol_update
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=True)
    status = Column(String, default="pending")  # pending / running / completed / failed
    search_keywords = Column(Text, nullable=True)  # JSON
    kols_found = Column(Integer, default=0)
    error_log = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    platform = relationship("Platform")


class OutreachCampaign(Base):
    __tablename__ = "outreach_campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=True)
    language = Column(String, default="zh")
    status = Column(String, default="draft")  # draft / active / paused / completed
    total_sent = Column(Integer, default=0)
    total_opened = Column(Integer, default=0)
    total_replied = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    template = relationship("EmailTemplate")
    emails = relationship("OutreachEmail", back_populates="campaign")


class OutreachEmail(Base):
    __tablename__ = "outreach_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("outreach_campaigns.id"), nullable=False)
    kol_id = Column(Integer, ForeignKey("kols.id"), nullable=False)
    to_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body_html = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending / sent / failed / opened / replied / bounced
    sent_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    follow_up_of = Column(Integer, ForeignKey("outreach_emails.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    campaign = relationship("OutreachCampaign", back_populates="emails")
    kol = relationship("KOL", back_populates="outreach_emails")


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    language = Column(String, default="zh")
    template_type = Column(String, default="initial_outreach")
    subject_template = Column(String, nullable=False)
    body_template = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    task_type = Column(String, nullable=False)  # full_scan / platform_scan / rescore / follow_up_check
    cron_expression = Column(String, nullable=False)
    platform_id = Column(Integer, ForeignKey("platforms.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    config_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    platform = relationship("Platform")
