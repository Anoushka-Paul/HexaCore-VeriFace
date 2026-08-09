# VeriFace

**AI-assisted face recognition and search system for law enforcement — matching sketches, photos, and CCTV footage against criminal and missing-persons databases.**

## Overview

VeriFace helps police reduce the time spent manually cross-referencing suspect sketches, photographs, or CCTV footage against existing records. An officer uploads a photo or sketch, and the system returns the closest matching faces from a database with a similarity score — flagged for human verification, never auto-confirmed. The same pipeline is reused to help locate missing persons.

## Problem

Identifying a suspect or a missing person today often means manually paging through physical or digital records — slow, error-prone, and hard to scale across large databases or hours of CCTV footage. VeriFace automates the *search*, while keeping the *decision* with a human officer.

## Features

- **Photo search** — upload a photo, get the top-5 closest matches from the database with a similarity percentage
- **Sketch search** — upload a hand-drawn or composite sketch; the system converts it to a photo-realistic image before matching, so sketch-based leads can be searched the same way as photos
- **CCTV scanning** — scan recorded footage from relevant cameras (e.g. stations, areas near a crime scene) for frame-level face matches against a target
- **Missing persons mode** — same search pipeline applied against a missing-persons database
- **Confidence-based verification** — every match is labeled *likely match / possible match / no match*; the system never auto-confirms an identity, it surfaces candidates for an officer to verify
- **Audit trail** — every search is logged (who searched, when, what was searched, what matched) for accountability
- **Camera map view** — CCTV matches are plotted by camera location and timestamp

## Architecture

┌─────────────┐ ┌──────────────────┐ ┌────────────────┐
│ Frontend │─────▶│ FastAPI Backend │─────▶│ FAISS Vector │
│ (React) │ │ │ │ Index │
└─────────────┘ │ - Face detection │ └────────────────┘
│ - ArcFace embed │
│ - Search + score │ ┌────────────────┐
│ - Audit logging │─────▶│ SQLite │
└──────────────────┘ │ (audit trail) │
▲ └────────────────┘
│
┌────────────┴────────────┐
│ Sketch → Photo (GAN) │
│ CCTV Frame Scanner │
└──────────────────────────┘

## Tech Stack

| Layer | Technology |
|---|---|
| Face detection & embeddings | InsightFace (ArcFace) |
| Vector search | FAISS |
| Sketch-to-photo conversion | Pretrained GAN (pix2pix/CycleGAN, CUFS/CUFSF-trained) |
| CCTV frame processing | OpenCV |
| Backend API | FastAPI |
| Audit storage | SQLite |
| Frontend | React (Vite) |
| Map view | Leaflet + OpenStreetMap |

## API Endpoints

- `POST /search` — upload an image (photo or converted sketch), returns top-5 matches with similarity % and confidence label
- `GET /audit` — returns the full search audit log
- `GET /cctv-results` — returns CCTV scan matches with timestamp, camera ID, and similarity %

## Responsible Use & Limitations

- **No automated identification.** All matches are candidates for human review, not confirmed identities.
- **Known bias risk.** Face recognition accuracy varies across demographics; the test set was chosen with this in mind, and any deployment would require a formal fairness audit before real-world use.
- **Data sensitivity.** Biometric data requires encrypted storage and role-based access control — implemented as a design consideration in this prototype, with hardening required for production use.
- **Prototype scope.** This was built as a hackathon proof of concept and is not deployment-ready without further security, privacy, and accuracy review.

## Roadmap

- Age progression modeling for long-term missing persons cases
- Real-time (live) CCTV stream processing
- End-to-end encryption for stored biometric data and full RBAC
- Formal bias/fairness evaluation across demographic groups

## Production Considerations

This is a hackathon prototype, built to prove the core concept works end to
end. A real deployment would require additional work in these areas:

- **Metadata storage**: SQLite is used here for simplicity. Production would
  use PostgreSQL for the audit log, case records, and person metadata, with
  proper indexing and backup/replication.
- **Vector search at scale**: FAISS's flat index works well at hundreds of
  faces but doesn't scale efficiently to millions. A production system would
  use a managed vector database (e.g. Pinecone, Milvus, or Postgres with
  pgvector) with approximate nearest-neighbor indexing.
- **Scalability**: Load balancing and async processing for concurrent
  officers submitting searches simultaneously, especially for CCTV video
  processing which is compute-intensive.
- **Bias & fairness auditing**: A formal accuracy evaluation across
  demographic groups before any real-world use, given known disparities in
  face recognition accuracy.

These were consciously deprioritized to focus build time on validating the
core recognition pipeline, confidence scoring, and audit logging first.