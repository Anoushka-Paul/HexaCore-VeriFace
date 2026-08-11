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
import tempfile
import uuid
from pathlib import Path
from threading import Lock
from datetime import datetime, timezone

import cv2
import faiss
import numpy as np
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from auth_service import auth_app, require_role
from insightface.app import FaceAnalysis
from cctv_scan import run_cctv_scan
from face_utils import DET_SIZE, MODEL_NAME, create_face_app, normalize_embedding, validate_single_face
from sketch_models.sketch_to_photo import convert_sketch_to_photo

# Paths are resolved relative to this file's location, not the current
# working directory — so `uvicorn` works the same regardless of which
# folder you launch it from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "face_index.faiss")
MAPPING_PATH = os.path.join(BASE_DIR, "face_mapping.json")
DB_PATH = os.path.join(BASE_DIR, "audit.db")
JOBS_DIR = Path(BASE_DIR) / "cctv_jobs"

# Load camera locations from JSON (small lookup for map UI later)
CAMERA_LOCATIONS_PATH = os.path.join(BASE_DIR, "camera_locations.json")
try:
    with open(CAMERA_LOCATIONS_PATH, "r", encoding="utf-8") as _cl:
        CAMERA_LOCATIONS = json.load(_cl)
except Exception:
    CAMERA_LOCATIONS = {}

# In-memory job status cache. Each job_id maps to a dict like:
# {"job_id": ..., "status": "processing"|'done'|'failed', ...}
JOBS_STATUS: dict[str, dict] = {}

TOP_K = 5
MIN_CANDIDATE_SIMILARITY = 0.50

app = FastAPI(title="VeriFace Search API")

# Mount the teammate's auth/case-management module under /auth.
# The auth package uses a separate SQLite file for user/case storage,
# while this root app continues to use audit.db for the face-search audit trail.
app.mount("/auth", auth_app)

# Mount the dataset static files so the frontend can load suspect images
app.mount("/dataset", StaticFiles(directory=os.path.join(BASE_DIR, "dataset")), name="dataset")

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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sightings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id TEXT,
            camera_id TEXT NOT NULL,
            lat REAL,
            lng REAL,
            label TEXT,
            timestamp TEXT NOT NULL,
            video_time_sec REAL,
            similarity REAL,
            job_id TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def backfill_jobs_status():
    """Scan `cctv_jobs` for existing status.json files and populate JOBS_STATUS."""
    if not JOBS_DIR.is_dir():
        return
    for child in JOBS_DIR.iterdir():
        if not child.is_dir():
            continue
        status_path = child / "status.json"
        if status_path.is_file():
            try:
                status = json.loads(status_path.read_text(encoding="utf-8"))
                job_id = status.get("job_id", child.name)
                JOBS_STATUS[job_id] = status
            except Exception:
                print(f"Warning: failed to read status for job {child.name}")


def get_camera_location(camera_id: str) -> dict | None:
    """Return a dict with lat/lng/label for a camera_id, or None if unknown."""
    return CAMERA_LOCATIONS.get(camera_id)


def persist_sightings(events: list[dict], camera_id: str, camera_loc: dict | None, job_id: str, person_id: str | None):
    conn = sqlite3.connect(DB_PATH)
    try:
        for ev in events:
            video_time = ev.get("start_sec")
            conn.execute(
                """
                INSERT INTO sightings (person_id, camera_id, lat, lng, label, timestamp, video_time_sec, similarity, job_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    person_id,
                    camera_id,
                    camera_loc.get("lat") if camera_loc else None,
                    camera_loc.get("lng") if camera_loc else None,
                    camera_loc.get("label") if camera_loc else None,
                    datetime.now(timezone.utc).isoformat(),
                    video_time,
                    ev.get("best_similarity"),
                    job_id,
                ),
            )
        conn.commit()
    finally:
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


def get_valid_category(category: str) -> str:
    if category not in {"all", "criminal", "missing_person"}:
        raise HTTPException(status_code=422, detail="category must be 'all', 'criminal', or 'missing_person'")
    return category


def search_image_bytes(contents: bytes, category: str = "all") -> list[dict]:
    file_bytes = np.frombuffer(contents, dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Could not read sketch output as an image")
    face, reason = validate_single_face(face_app.get(img))
    if reason:
        raise HTTPException(status_code=422, detail=reason)
    query_embedding = normalize_embedding(face.embedding)
    return serialize_results(query_embedding, category)


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
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    # Backfill missing `category` for older mappings. Default to 'criminal'.
    updated = False
    for entry in mapping:
        if "category" not in entry:
            entry["category"] = "criminal"
            updated = True
    if updated:
        print("Backfilling missing 'category' in mapping and saving...")
        with open(MAPPING_PATH, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)

    print("Initializing audit database...")
    init_db()

    print(f"Ready. Index has {index.ntotal} faces, mapping has {len(mapping)} entries.")

    # Backfill in-memory job status from any existing on-disk job status files.
    backfill_jobs_status()


def confidence_label(similarity: float) -> str:
    if similarity > 0.75:
        return "likely match"
    elif similarity >= 0.5:
        return "possible match"
    else:
        return "no match"


def serialize_results(query_embedding: np.ndarray, category: str = "all") -> list[dict]:
    """Group all exact FAISS reference scores into one candidate per person."""
    similarities, indices = index.search(query_embedding, index.ntotal)
    people: dict[str, dict] = {}
    for similarity, idx in zip(similarities[0], indices[0]):
        if idx == -1:
            continue
        entry = mapping[idx]
        entry_category = entry.get("category", "criminal")
        if category != "all" and entry_category != category:
            continue
        sim = float(similarity)
        person = people.setdefault(entry["person_id"], {
            "person_id": entry["person_id"], "name": entry["name"],
            "category": entry_category,
            "similarity": sim, "best_reference": entry["filename"], "reference_count": 0,
        })
        person["reference_count"] += 1
        if sim > person["similarity"]:
            person["similarity"] = sim
            person["best_reference"] = entry["filename"]
            # If mapping carries category per reference, update person's category
            person["category"] = entry_category
    ranked = sorted(people.values(), key=lambda person: person["similarity"], reverse=True)[:TOP_K]
    for person in ranked:
        person["similarity"] = round(person["similarity"], 4)
        person["confidence"] = confidence_label(person["similarity"])
        person["review_recommended"] = person["similarity"] >= MIN_CANDIDATE_SIMILARITY
    return ranked


@app.post("/search")
async def search(
    file: UploadFile = File(...),
    category: str = Form("all", description="Filter by category: all, criminal, or missing_person"),
    current_user=Depends(require_role("officer", "admin")),
):
    if index is None or mapping is None or face_app is None:
        raise HTTPException(status_code=503, detail="Server not ready yet")

    contents = await file.read()
    category = get_valid_category(category)
    file_bytes = np.frombuffer(contents, dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(status_code=400, detail="Could not read uploaded file as an image")

    face, reason = validate_single_face(face_app.get(img))
    if reason:
        log_search(file.filename, None)  # still log failed searches for the audit trail
        raise HTTPException(status_code=422, detail=reason)
    query_embedding = normalize_embedding(face.embedding)
    results = serialize_results(query_embedding, category)

    log_search(file.filename, results[0] if results else None)

    return results


@app.post("/add-person")
async def add_person(
    person_id: str | None = Form(None, description="Optional person_id. If omitted, a new person ID is generated."),
    name: str = Form(...),
    category: str = Form(..., description="criminal | missing_person"),
    file: UploadFile = File(...),
    current_user=Depends(require_role("admin")),
):
    """
    Adds a new person or a new reference image for an existing person.
    If person_id is omitted, a new person record is created automatically.
    Reusing an existing person_id is allowed when the name matches.
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
    category = get_valid_category(category)
    if category == "all":
        raise HTTPException(status_code=422, detail="category must be 'criminal' or 'missing_person' for add-person")
    embedding = normalize_embedding(face.embedding)

    with index_lock:
        if person_id is None or person_id == "":
            person_id = uuid.uuid4().hex
            existing = []
        else:
            existing = [entry for entry in mapping if entry["person_id"] == person_id]
            if existing and any(entry["name"].casefold() != name.casefold() for entry in existing):
                raise HTTPException(status_code=409, detail=f"person_id '{person_id}' already belongs to '{existing[0]['name']}'")

        index.add(embedding)
        mapping.append({
            "person_id": person_id,
            "name": name,
            "filename": file.filename,
            "category": category,
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


@app.post("/sketch-search")
async def sketch_search(
    sketch: UploadFile = File(..., description="Hand-drawn sketch image for conversion and matching"),
    style: str = Form("cufs", description="Sketch conversion style: cufs or cufsf"),
    category: str = Form("all", description="Filter by category: all, criminal, or missing_person"),
    current_user=Depends(require_role("officer", "admin")),
):
    if style not in {"cufs", "cufsf"}:
        raise HTTPException(status_code=422, detail="style must be 'cufs' or 'cufsf'")
    category = get_valid_category(category)

    import base64
    converted_base64 = ""

    with tempfile.TemporaryDirectory() as tmp_dir:
        sketch_path = Path(tmp_dir) / "sketch.png"
        converted_path = Path(tmp_dir) / "converted.jpg"
        await persist_upload(sketch, sketch_path)
        try:
            convert_sketch_to_photo(str(sketch_path), str(converted_path), style=style)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        converted_bytes = Path(converted_path).read_bytes()
        converted_base64 = base64.b64encode(converted_bytes).decode("utf-8")

    results = search_image_bytes(converted_bytes, category)
    return {
        "search_type": "sketch",
        "style": style,
        "category": category,
        "converted_image": f"data:image/jpeg;base64,{converted_base64}",
        "results": results,
    }


@app.post("/cctv-scan")
async def cctv_scan(
    video: UploadFile = File(..., description="Recorded CCTV video, such as MP4"),
    target: UploadFile = File(..., description="Clear reference photo of the target"),
    camera_id: str = Form("cam_1"),
    interval: float = Form(0.5),
    threshold: float = Form(0.45),
    background_tasks: BackgroundTasks = None,
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

    # Create job folder and persist uploads immediately, then run the
    # heavy work in a BackgroundTasks worker so we can return instantly.
    job_id = uuid.uuid4().hex
    job_dir = JOBS_DIR / job_id
    evidence_dir = job_dir / "evidence"
    job_dir.mkdir(parents=True, exist_ok=False)
    video_path, target_path = job_dir / f"source{video_suffix}", job_dir / f"target{target_suffix}"
    await persist_upload(video, video_path)
    await persist_upload(target, target_path)

    # Initialize job status (persisted and in-memory)
    status_obj = {"job_id": job_id, "status": "processing"}
    JOBS_STATUS[job_id] = status_obj
    (job_dir / "status.json").write_text(json.dumps(status_obj), encoding="utf-8")

    # Schedule background worker
    def _cctv_worker(job_id: str, job_dir: Path, video_path: str, target_path: str, camera_id: str, interval: float, threshold: float):
        try:
            evidence_dir = job_dir / "evidence"

            # Attempt to resolve target -> person_id using the server's FAISS index.
            person_id = None
            try:
                # Read target image and compute embedding using the loaded face_app
                import cv2 as _cv2
                img = _cv2.imread(str(target_path))
                if img is not None and face_app is not None:
                    face_obj, reason = validate_single_face(face_app.get(img))
                    if not reason and face_obj is not None:
                        target_embedding = normalize_embedding(face_obj.embedding)
                        top_people = serialize_results(target_embedding)
                        if top_people:
                            person_id = top_people[0].get("person_id")
            except Exception:
                # Non-fatal: if we cannot resolve person_id, continue without it
                person_id = None

            cam_loc = get_camera_location(camera_id)
            results = run_cctv_scan(
                str(video_path), str(target_path), camera_id, interval, threshold,
                str(evidence_dir), str(job_dir / "review.mp4"),
                camera_location=cam_loc,
            )

            # Persist sightings for each event. If persistence fails, do not mark the job as done.
            persist_sightings(results.get("events", []), camera_id, cam_loc, job_id, person_id)

            # Add artifact URLs and save results
            evidence_urls = [f"/cctv-jobs/{job_id}/evidence/{match['evidence_image']}" for match in results["matches"]]
            results["input"]["video"] = Path(video_path).name
            results["input"]["camera_location"] = cam_loc
            results["input"]["resolved_person_id"] = person_id
            results["status"] = "done"
            results["artifacts"] = {
                "results_url": f"/cctv-jobs/{job_id}/results",
                "review_video_url": f"/cctv-jobs/{job_id}/review-video",
                "evidence_urls": evidence_urls,
            }
            (job_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
            status_obj = {"job_id": job_id, "status": "done"}
            (job_dir / "status.json").write_text(json.dumps(status_obj), encoding="utf-8")
            JOBS_STATUS[job_id] = status_obj
        except Exception as exc:
            err = str(exc)
            status_obj = {"job_id": job_id, "status": "failed", "error": err}
            (job_dir / "status.json").write_text(json.dumps(status_obj), encoding="utf-8")
            JOBS_STATUS[job_id] = status_obj

    # Add to FastAPI BackgroundTasks so the worker runs after response
    if background_tasks is None:
        # Defensive: if BackgroundTasks not provided, run in a thread via add_task still expects it; raise to be explicit
        raise HTTPException(status_code=500, detail="BackgroundTasks not available")
    background_tasks.add_task(_cctv_worker, job_id, job_dir, str(video_path), str(target_path), camera_id, interval, threshold)

    return {"job_id": job_id, "status": "processing"}


@app.get("/cctv-jobs/{job_id}/results")
def get_cctv_results(job_id: str, current_user=Depends(require_role("officer", "admin"))):
    job_dir = job_directory(job_id)
    status_path = job_dir / "status.json"
    results_path = job_dir / "results.json"

    if status_path.is_file():
        status = json.loads(status_path.read_text(encoding="utf-8"))
    else:
        # Fall back to in-memory status if available
        status = JOBS_STATUS.get(job_id, {"job_id": job_id, "status": "unknown"})

    if status["status"] == "processing":
        return status
    if status["status"] == "failed":
        return status
    if results_path.is_file():
        results = json.loads(results_path.read_text(encoding="utf-8"))
        if status["status"] == "done":
            results["status"] = "done"
        return results
    # If marked done but file missing, return status to indicate finalization issue
    return status


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


@app.get("/sightings")
def query_sightings(
    person_id: str | None = None,
    camera_id: str | None = None,
    current_user=Depends(require_role("officer", "admin")),
):
    query = "SELECT * FROM sightings"
    params: list = []
    filters: list[str] = []
    if person_id:
        filters.append("person_id = ?")
        params.append(person_id)
    if camera_id:
        filters.append("camera_id = ?")
        params.append(camera_id)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY timestamp DESC"

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/camera-locations")
def camera_locations(current_user=Depends(require_role("officer", "admin"))):
    return CAMERA_LOCATIONS


@app.get("/health")
def health():
    return {
        "status": "ok",
        "index_size": index.ntotal if index else 0,
        "face_model": MODEL_NAME,
        "detector_size": DET_SIZE,
    }
