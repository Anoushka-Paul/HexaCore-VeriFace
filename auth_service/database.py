"""
Database setup for VeriFace auth/case-management service.
Uses SQLite for the hackathon; swap DATABASE_URL for Postgres later if needed.
"""
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, ForeignKey
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./veriface_auth.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="officer")  # "officer" | "admin"
    created_at = Column(DateTime, default=datetime.utcnow)

    cases = relationship("Case", back_populates="creator")


class Case(Base):
    __tablename__ = "cases"

    case_id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", back_populates="cases")
    audit_links = relationship("CaseAuditLink", back_populates="case")


class CaseAuditLink(Base):
    """
    Links a search-audit entry (from the teammate's FastAPI search service,
    GET /audit) to a case. We store the audit entry's ID/reference here
    rather than duplicating audit data — this service just tracks the
    association.
    """
    __tablename__ = "case_audit_links"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.case_id"), nullable=False)
    audit_ref = Column(String, nullable=False)  # ID/reference from GET /audit
    linked_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    linked_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="audit_links")


class Person(Base):
    """Records added to the searchable face database (admin-only)."""
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    external_id = Column(String, nullable=False)  # ID number / badge / case ref
    image_path = Column(String, nullable=False)
    added_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
