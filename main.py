"""
main.py

FastAPI backend for VeriFace face search, with a SQLite audit trail.
Loads a prebuilt FAISS index + mapping file at startup, exposes:
    POST /search      - upload an image, get top-5 matches, logs the search
    POST /add-person   - add a person or another reference image for one
    POST /cctv-scan    - scan uploaded video and return review artifacts
    GET  /audit        - view the full search audit log
    GET  /health        - basic status check

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import json
import os
import sqlite3
import uuid
from pathlib import Path
from threading import Lock
from datetime import datetime, timezone

import cv2
import faiss
import numpy as np
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from auth_service import auth_app, require_role
from insightface.app import FaceAnalysis
from cctv_scan import run_cctv_scan
from face_utils import DET_SIZE, MODEL_NAME, create_face_app, normalize_embedding, validate_single_face

# Paths are resolved relative to this file's location, not the current
# working directory — so `uvicorn` works the same regardless of which
# folder you launch it from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "face_index.faiss")
MAPPING_PATH = os.path.join(BASE_DIR, "face_mapping.json")
DB_PATH = os.path.join(BASE_DIR, "audit.db")
JOBS_DIR = Path(BASE_DIR) / "cctv_jobs"

TOP_K = 5
MIN_CANDIDATE_SIMILARITY = 0.50

app = FastAPI(title="VeriFace Search API")

# Mount the teammate's auth/case-management module under /auth.
# The auth package uses a separate SQLite file for user/case storage,
# while this root app continues to use audit.db for the face-search audit trail.
app.mount("/auth", auth_app)

# NOTE: allow_origins=["*"] is fine for a hackathon demo (any frontend origin
# can call this API). For a real deployment this should be locked down to the
# actual frontend's origin, e.g. allow_origins=["https://veriface.example.com"].
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- loaded once at startup ---
face_app: FaceAnalysis | None = None
index: faiss.Index | None = None
mapping: list[dict] | None = None
index_lock = Lock()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            filename TEXT NOT NULL,
            top_match_person_id TEXT,
            top_match_name TEXT,
            similarity REAL,
            confidence TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_search(filename: str, top_result: dict | None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO audit_log (timestamp, filename, top_match_person_id, top_match_name, similarity, confidence)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            filename,
            top_result["person_id"] if top_result else None,
            top_result["name"] if top_result else None,
            top_result["similarity"] if top_result else None,
            top_result["confidence"] if top_result else None,
        ),
    )
    conn.commit()
    conn.close()


def save_index_and_mapping():
    faiss.write_index(index, INDEX_PATH)
    with open(MAPPING_PATH, "w") as f:
        json.dump(mapping, f, indent=2)


def job_directory(job_id: str) -> Path:
    if len(job_id) != 32 or any(char not in "0123456789abcdef" for char in job_id):
        raise HTTPException(status_code=404, detail="CCTV job not found")
    path = JOBS_DIR / job_id
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="CCTV job not found")
    return path


async def persist_upload(upload: UploadFile, destination: Path) -> None:
    contents = await upload.read()
    if not contents:
        raise HTTPException(status_code=422, detail=f"'{upload.filename}' is empty")
    destination.write_bytes(contents)


@app.on_event("startup")
def load_resources():
    global face_app, index, mapping

    print("Loading insightface model...")
    face_app = create_face_app()

    print(f"Loading FAISS index from {INDEX_PATH}...")
    index = faiss.read_index(INDEX_PATH)

    print(f"Loading mapping from {MAPPING_PATH}...")
    with open(MAPPING_PATH, "r") as f:
        mapping = json.load(f)

    print("Initializing audit database...")
    init_db()

    print(f"Ready. Index has {index.ntotal} faces, mapping has {len(mapping)} entries.")


def confidence_label(similarity: float) -> str:
    if similarity > 0.75:
        return "likely match"
    elif similarity >= 0.5:
        return "possible match"
    else:
        return "no match"


def serialize_results(query_embedding: np.ndarray) -> list[dict]:
    """Group all exact FAISS reference scores into one candidate per person."""
    similarities, indices = index.search(query_embedding, index.ntotal)
    people: dict[str, dict] = {}
    for similarity, idx in zip(similarities[0], indices[0]):
        if idx == -1:
            continue
        entry = mapping[idx]
        sim = float(similarity)
        person = people.setdefault(entry["person_id"], {
            "person_id": entry["person_id"], "name": entry["name"],
            "similarity": sim, "best_reference": entry["filename"], "reference_count": 0,
        })
        person["reference_count"] += 1
        if sim > person["similarity"]:
            person["similarity"] = sim
            person["best_reference"] = entry["filename"]
    ranked = sorted(people.values(), key=lambda person: person["similarity"], reverse=True)[:TOP_K]
    for person in ranked:
        person["similarity"] = round(person["similarity"], 4)
        person["confidence"] = confidence_label(person["similarity"])
        person["review_recommended"] = person["similarity"] >= MIN_CANDIDATE_SIMILARITY
    return ranked


@app.post("/search")
async def search(
    file: UploadFile = File(...),
    current_user=Depends(require_role("officer", "admin")),
):
    if index is None or mapping is None or face_app is None:
        raise HTTPException(status_code=503, detail="Server not ready yet")

    contents = await file.read()
    file_bytes = np.frombuffer(contents, dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Could not read uploaded file as an image")

    face, reason = validate_single_face(face_app.get(img))
    if reason:
        log_search(file.filename, None)  # still log failed searches for the audit trail
        raise HTTPException(status_code=422, detail=reason)
    query_embedding = normalize_embedding(face.embedding)
    results = serialize_results(query_embedding)

    log_search(file.filename, results[0] if results else None)

    return results


@app.post("/add-person")
async def add_person(
    person_id: str = Form(...),
    name: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(require_role("admin")),
):
    """
    Adds a new reference to a person. Reusing an existing person_id is allowed
    when the name matches, so each person can have several reference images.
    """
    if index is None or mapping is None or face_app is None:
        raise HTTPException(status_code=503, detail="Server not ready yet")

    contents = await file.read()
    file_bytes = np.frombuffer(contents, dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Could not read uploaded file as an image")

    face, reason = validate_single_face(face_app.get(img))
    if reason:
        raise HTTPException(status_code=422, detail=reason)
    embedding = normalize_embedding(face.embedding)
    # Keep the vector index and its positional mapping atomically aligned.
    with index_lock:
        existing = [entry for entry in mapping if entry["person_id"] == person_id]
        if existing and any(entry["name"].casefold() != name.casefold() for entry in existing):
            raise HTTPException(status_code=409, detail=f"person_id '{person_id}' already belongs to '{existing[0]['name']}'")
        index.add(embedding)
        mapping.append({
            "person_id": person_id,
            "name": name,
            "filename": file.filename,
        })
        save_index_and_mapping()

    return {
        "status": "reference_added" if existing else "person_added",
        "person_id": person_id,
        "name": name,
        "total_people_in_database": len({entry["person_id"] for entry in mapping}),
        "total_reference_images": index.ntotal,
        "reference_count_for_person": len(existing) + 1,
    }


@app.post("/cctv-scan")
async def cctv_scan(
    video: UploadFile = File(..., description="Recorded CCTV video, such as MP4"),
    target: UploadFile = File(..., description="Clear reference photo of the target"),
    camera_id: str = Form("cam_1"),
    interval: float = Form(0.5),
    threshold: float = Form(0.45),
    current_user=Depends(require_role("officer", "admin")),
):
    """Scan one uploaded video and return candidate frames/events plus review artifacts."""
    if interval <= 0 or not 0 <= threshold <= 1:
        raise HTTPException(status_code=422, detail="interval must be positive and threshold must be between 0 and 1")
    video_suffix = Path(video.filename or "video.mp4").suffix.lower()
    target_suffix = Path(target.filename or "target.jpg").suffix.lower()
    if video_suffix not in {".mp4", ".avi", ".mov", ".mkv"}:
        raise HTTPException(status_code=415, detail="Unsupported video format; use MP4, AVI, MOV, or MKV")
    if target_suffix not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=415, detail="Target image must be JPG, JPEG, or PNG")

    job_id = uuid.uuid4().hex
    job_dir = JOBS_DIR / job_id
    evidence_dir = job_dir / "evidence"
    job_dir.mkdir(parents=True, exist_ok=False)
    video_path, target_path = job_dir / f"source{video_suffix}", job_dir / f"target{target_suffix}"
    await persist_upload(video, video_path)
    await persist_upload(target, target_path)
    try:
        results = run_cctv_scan(
            str(video_path), str(target_path), camera_id, interval, threshold,
            str(evidence_dir), str(job_dir / "review.mp4"),
        )
    except (SystemExit, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    evidence_urls = [f"/cctv-jobs/{job_id}/evidence/{match['evidence_image']}" for match in results["matches"]]
    results["input"]["video"] = video.filename
    results["artifacts"] = {
        "results_url": f"/cctv-jobs/{job_id}/results",
        "review_video_url": f"/cctv-jobs/{job_id}/review-video",
        "evidence_urls": evidence_urls,
    }
    (job_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return {"job_id": job_id, "status": "complete", **results}


@app.get("/cctv-jobs/{job_id}/results")
def get_cctv_results(job_id: str, current_user=Depends(require_role("officer", "admin"))):
    result_path = job_directory(job_id) / "results.json"
    if not result_path.is_file():
        raise HTTPException(status_code=404, detail="CCTV results not found")
    return json.loads(result_path.read_text(encoding="utf-8"))


@app.get("/cctv-jobs/{job_id}/review-video")
def get_cctv_review_video(job_id: str, current_user=Depends(require_role("officer", "admin"))):
    review_path = job_directory(job_id) / "review.mp4"
    if not review_path.is_file():
        raise HTTPException(status_code=404, detail="Annotated review video not found")
    return FileResponse(review_path, media_type="video/mp4", filename=f"cctv_review_{job_id}.mp4")


@app.get("/cctv-jobs/{job_id}/evidence/{filename}")
def get_cctv_evidence(job_id: str, filename: str, current_user=Depends(require_role("officer", "admin"))):
    if Path(filename).name != filename:
        raise HTTPException(status_code=404, detail="Evidence image not found")
    evidence_path = job_directory(job_id) / "evidence" / filename
    if not evidence_path.is_file():
        raise HTTPException(status_code=404, detail="Evidence image not found")
    return FileResponse(evidence_path, media_type="image/jpeg", filename=filename)


@app.get("/audit")
def get_audit_log(current_user=Depends(require_role("admin"))):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()

    return [dict(row) for row in rows]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "index_size": index.ntotal if index else 0,
        "face_model": MODEL_NAME,
        "detector_size": DET_SIZE,
    }
