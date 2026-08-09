"""
main.py

FastAPI backend for VeriFace face search, with a SQLite audit trail.
Loads a prebuilt FAISS index + mapping file at startup, exposes:
    POST /search      - upload an image, get top-5 matches, logs the search
    POST /add-person   - add a new person to the database (embeds + appends to FAISS)
    GET  /audit        - view the full search audit log
    GET  /health        - basic status check

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

import cv2
import faiss
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from insightface.app import FaceAnalysis

# Paths are resolved relative to this file's location, not the current
# working directory — so `uvicorn` works the same regardless of which
# folder you launch it from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "face_index.faiss")
MAPPING_PATH = os.path.join(BASE_DIR, "face_mapping.json")
DB_PATH = os.path.join(BASE_DIR, "audit.db")

DET_SIZE = (160, 160)  # small det_size works better for tightly-cropped face images
TOP_K = 5

app = FastAPI(title="VeriFace Search API")

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


@app.on_event("startup")
def load_resources():
    global face_app, index, mapping

    print("Loading insightface model...")
    face_app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    face_app.prepare(ctx_id=0, det_size=DET_SIZE)

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


@app.post("/search")
async def search(file: UploadFile = File(...)):
    if index is None or mapping is None or face_app is None:
        raise HTTPException(status_code=503, detail="Server not ready yet")

    contents = await file.read()
    file_bytes = np.frombuffer(contents, dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Could not read uploaded file as an image")

    faces = face_app.get(img)

    if len(faces) == 0:
        log_search(file.filename, None)  # still log failed searches for the audit trail
        raise HTTPException(status_code=422, detail="No face detected in uploaded image")

    # if multiple faces in the query image, use the largest one
    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    query_embedding = face.embedding.astype("float32").reshape(1, -1)
    faiss.normalize_L2(query_embedding)

    k = min(TOP_K, index.ntotal)
    similarities, indices = index.search(query_embedding, k)

    results = []
    for similarity, idx in zip(similarities[0], indices[0]):
        if idx == -1:
            continue
        entry = mapping[idx]
        sim = float(similarity)
        results.append({
            "person_id": entry["person_id"],
            "name": entry["name"],
            "similarity": round(sim, 4),
            "confidence": confidence_label(sim),
        })

    log_search(file.filename, results[0] if results else None)

    return results


@app.post("/add-person")
async def add_person(
    person_id: str = Form(...),
    name: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Adds a new person to the searchable database: embeds the uploaded photo
    and appends it to the live FAISS index + mapping, then persists both to
    disk so the addition survives a server restart.
    """
    if index is None or mapping is None or face_app is None:
        raise HTTPException(status_code=503, detail="Server not ready yet")

    # prevent duplicate IDs so the mapping stays unambiguous
    if any(entry["person_id"] == person_id for entry in mapping):
        raise HTTPException(status_code=409, detail=f"person_id '{person_id}' already exists")

    contents = await file.read()
    file_bytes = np.frombuffer(contents, dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Could not read uploaded file as an image")

    faces = face_app.get(img)

    if len(faces) == 0:
        raise HTTPException(status_code=422, detail="No face detected in uploaded image")

    face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    embedding = face.embedding.astype("float32").reshape(1, -1)
    faiss.normalize_L2(embedding)

    index.add(embedding)
    mapping.append({
        "person_id": person_id,
        "name": name,
        "filename": file.filename,
    })

    save_index_and_mapping()

    return {
        "status": "added",
        "person_id": person_id,
        "name": name,
        "total_people_in_database": index.ntotal,
    }


@app.get("/audit")
def get_audit_log():
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
    }