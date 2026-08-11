"""
VeriFace — Auth & Case Management service.
Runs standalone on port 8001. Wire to teammate's search service
(localhost:8000, POST /search, GET /audit) via the /cases/{case_id}/link-audit
endpoint, which just stores a reference — it doesn't call that service directly,
so the two stay decoupled until you want to join them.
"""
import os
import shutil
import uuid
from datetime import timedelta
from typing import List

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from .database import init_db, get_db, SessionLocal, User, Case, CaseAuditLink, Person
from .models import (
    Token, UserCreate, UserOut, CaseCreate, CaseOut,
    AuditLinkCreate, AuditLinkOut, PersonOut
)
from .auth import (
    authenticate_user, create_access_token, hash_password,
    get_current_user, require_role, ACCESS_TOKEN_EXPIRE_MINUTES
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="VeriFace Auth & Case Management")


@app.on_event("startup")
def on_startup():
    init_db()


# ============================================================
# AUTH
# ============================================================

@app.post("/register", response_model=UserOut)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Dev/setup helper to create users. In a real deployment you'd lock this
    down (e.g. admin-only, or remove entirely and seed users via a script)
    rather than leaving open registration on an internal police tool.
    """
    existing = db.query(User).filter(User.username == user_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        username=user_in.username,
        hashed_password=hash_password(user_in.password),
        role=user_in.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login", response_model=Token)
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token, role=user.role)


@app.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user


# ============================================================
# CASES  (any authenticated user — officer or admin)
# ============================================================

@app.post("/cases", response_model=CaseOut)
def create_case(
    case_in: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = Case(description=case_in.description, created_by=current_user.id)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@app.get("/cases", response_model=List[CaseOut])
def list_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(Case).order_by(Case.created_at.desc()).all()


@app.get("/cases/{case_id}", response_model=CaseOut)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.post("/cases/{case_id}/link-audit", response_model=AuditLinkOut)
def link_audit_to_case(
    case_id: int,
    link_in: AuditLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Associates a search-audit entry (by its reference/ID from the search
    service's GET /audit) with a case. This service doesn't fetch the audit
    entry itself — the frontend/orchestration layer can join the two calls
    once both services are wired together.
    """
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    link = CaseAuditLink(
        case_id=case_id,
        audit_ref=link_in.audit_ref,
        linked_by=current_user.id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@app.get("/cases/{case_id}/audit-links", response_model=List[AuditLinkOut])
def list_case_audit_links(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return db.query(CaseAuditLink).filter(CaseAuditLink.case_id == case_id).all()


# ============================================================
# ADMIN-ONLY: face database management
# ============================================================

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@app.post("/database/add-person", response_model=PersonOut)
def add_person(
    name: str = Form(...),
    external_id: str = Form(...),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """
    Admin-only. Saves the uploaded photo to disk and records a Person row.
    Teammate's FAISS index rebuild is a separate offline/async step that
    can scan this uploads folder (or listen for new Person rows).
    """
    if photo.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {photo.content_type}. Use JPEG, PNG, or WEBP.",
        )

    ext = os.path.splitext(photo.filename or "")[1] or ".jpg"
    safe_filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(dest_path, "wb") as f:
        shutil.copyfileobj(photo.file, f)

    person = Person(
        name=name,
        external_id=external_id,
        image_path=dest_path,
        added_by=current_user.id,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@app.get("/database/persons", response_model=List[PersonOut])
def list_persons(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    return db.query(Person).order_by(Person.added_at.desc()).all()


# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("auth_service.router:app", host="0.0.0.0", port=8001, reload=True)
