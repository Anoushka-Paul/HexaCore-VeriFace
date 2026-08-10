from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# --- Auth ---------------------------------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = Field(default="officer", pattern="^(officer|admin)$")


class UserOut(BaseModel):
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True


# --- Cases -----------------------------------------------------------
class CaseCreate(BaseModel):
    description: str


class CaseOut(BaseModel):
    case_id: int
    description: str
    created_by: int
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLinkCreate(BaseModel):
    audit_ref: str  # the ID/reference returned by teammate's GET /audit


class AuditLinkOut(BaseModel):
    id: int
    case_id: int
    audit_ref: str
    linked_by: int
    linked_at: datetime

    class Config:
        from_attributes = True


# --- Persons (face DB) ---------------------------------------------
class PersonOut(BaseModel):
    id: int
    name: str
    external_id: str
    image_path: str
    added_by: int
    added_at: datetime

    class Config:
        from_attributes = True
