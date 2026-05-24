import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class KnownError(Base):
    __tablename__ = "known_errors"

    id = Column(Integer, primary_key=True)
    error_type = Column(String(100))
    pattern = Column(Text, nullable=False)
    log_keywords = Column(ARRAY(Text))
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class RootCause(Base):
    __tablename__ = "root_causes"

    id = Column(Integer, primary_key=True)
    known_error_id = Column(Integer, ForeignKey("known_errors.id"))
    description = Column(Text, nullable=False)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Solution(Base):
    __tablename__ = "solutions"

    id = Column(Integer, primary_key=True)
    root_cause_id = Column(Integer, ForeignKey("root_causes.id"))
    title = Column(String(255))
    description = Column(Text, nullable=False)
    steps = Column(JSONB)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True)
    pod_name = Column(String(255))
    namespace = Column(String(255))
    pod_logs = Column(Text)
    error_pattern = Column(Text)
    rca_summary = Column(Text)
    solution_summary = Column(Text)
    full_report = Column(Text)
    notification_sent = Column(Boolean, default=False)
    slack_sent = Column(Boolean, default=False)
    email_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
