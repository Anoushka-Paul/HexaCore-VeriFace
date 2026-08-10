# VeriFace

**AI-assisted face recognition and search system for law enforcement — matching sketches, photos, and CCTV footage against criminal and missing-persons databases.**

## Overview

VeriFace helps police reduce the time spent manually cross-referencing suspect sketches, photographs, or CCTV footage against existing records. An officer uploads a photo or sketch, and the system returns closest candidates with a similarity score — flagged for human verification, never auto-confirmed. The same pipeline supports missing-person searches.

## Features

- **Photo search** — upload a photo and get the top five candidate matches.
- **Sketch search** — sketch-to-photo conversion is being integrated by the team so generated search images can use the same face-search pipeline.
- **CCTV scanning** — scan recorded footage for frame-level candidates, with evidence crops, timestamps, and an annotated review video.
- **Missing persons mode** — reuse the search pipeline against a missing-persons database.
- **Confidence-based verification** — every result remains a human-review candidate.
- **Audit trail** — every image search is logged in SQLite.
- **Camera map view** — CCTV matches can be plotted by camera location and timestamp as the map component is integrated.

## Architecture

```text
React frontend / Sketch-to-photo module / CCTV scanner
                     │
                     ▼
              FastAPI backend
       detection + ArcFace embedding + scoring
              │                 │
              ▼                 ▼
        FAISS vector index    SQLite audit log
```

## Tech stack

| Layer | Technology |
|---|---|
| Face detection & embeddings | InsightFace `buffalo_l` (ArcFace) |
| Vector search | FAISS exact cosine search |
| Sketch-to-photo conversion | Team-integrated pretrained GAN workflow |
| CCTV frame processing | OpenCV |
| Backend API | FastAPI |
| Audit storage | SQLite |
| Frontend / map | React (Vite), Leaflet + OpenStreetMap |

## Setup

```powershell
pip install -r requirements.txt
python build_index.py --input dataset
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Image search and multiple references

`POST /search` returns the nearest five **people**, not duplicate images. Each result includes the best reference image and the count of references used for that person. `POST /add-person` can create a person or add another reference by reusing the same `person_id` and name.

For batch indexing, either form works:

```text
dataset/001_Jane_Doe.jpg                 # legacy: one reference
dataset/001_Jane_Doe__02.jpg             # flat multi-reference form
dataset/001_Jane_Doe/reference_01.jpg    # preferred multi-reference form
dataset/001_Jane_Doe/reference_02.jpg
```

When rebuilding the legacy flat demo dataset, repeated names (for example the
several George W. Bush images) are automatically consolidated under the first
person ID while every image remains a separate reference vector.

Reference inputs must contain exactly one sufficiently clear face. The API rejects ambiguous, tiny, and low-confidence faces rather than silently embedding them. Photo search/indexing use a 320px detector; CCTV uses 640px plus enlarged tiled recovery for wide frames.

## CCTV workflow

```powershell
python create_cctv_demo.py
python cctv_scan.py --video demo_cctv_simulated.mp4 --target demo_assets\fictional_suspect_reference.jpg --camera-id demo_corridor --interval 0.5 --threshold 0.45
```

This produces `cctv_results.json`, cropped evidence in `cctv_evidence/`, and an annotated `cctv_review.mp4`. The included footage is explicitly labelled synthetic test footage.

The API accepts the same inputs:

```powershell
curl.exe -X POST http://127.0.0.1:8000/cctv-scan `
  -F "video=@demo_cctv_simulated.mp4" `
  -F "target=@demo_assets\fictional_suspect_reference.jpg" `
  -F "camera_id=demo_corridor" `
  -F "interval=0.5" `
  -F "threshold=0.45"
```

The response contains `matches` (frame number, timestamp, score, face box), grouped `events` (`start_sec`, `end_sec`, best frame), and URLs for the saved JSON, evidence crops, and annotated MP4.

## API endpoints

- `POST /search` — upload a photo or an image produced by the sketch module; returns the top five people.
- `POST /add-person` — add a new person or an additional reference image for an existing person.
- `POST /cctv-scan` — upload CCTV video and target image; returns timestamps, candidate events, and artifact URLs.
- `GET /cctv-jobs/{job_id}/results` — retrieve the saved scan JSON.
- `GET /cctv-jobs/{job_id}/review-video` — download the annotated review MP4.
- `GET /audit` — returns the image-search audit log.
- `GET /health` — status, index size, and active model configuration.
- `POST /auth/register` — create a new user for local/dev setup.
- `POST /auth/login` — obtain a bearer token for protected routes.
- `GET /auth/me` — view the currently authenticated user.

## Authentication

The API now uses JWT bearer auth for all operational workflows. `POST /search`, `POST /cctv-scan`, and CCTV evidence retrieval require an authenticated officer or admin. `POST /add-person` and `GET /audit` are restricted to admin users only.

## Responsible use and production considerations

- **No automated identification.** Scores are candidate leads for human verification only.
- **Threshold calibration matters.** The `0.50` review threshold is a demo default, not an operational identity threshold.
- **SQLite is sufficient now.** Keep SQLite for the MVP audit log and FAISS plus `face_mapping.json` for the small reference collection. Move to PostgreSQL/object storage and a managed vector service only when concurrent users, retention, backups, or collection size require it.
- A real deployment needs role-based access, encryption, retention controls, tamper-evident logs, demographic evaluation, false-positive testing, legal review, and queued processing for long CCTV scans.

## Roadmap

- Age progression modelling for long-term missing-person cases
- Live CCTV stream processing
- End-to-end encryption and full RBAC
- Formal bias/fairness evaluation
