"""Shared face-model configuration and input-quality checks for VeriFace."""

import os
import numpy as np
from pathlib import Path
from insightface.app import FaceAnalysis

MODEL_NAME = "buffalo_l"
# 320 is reliable for normal uploaded/reference portraits, including the
# 250px development images. CCTV overrides this to 640 for wide frames.
DET_SIZE = (320, 320)
MIN_DETECTION_SCORE = 0.65
MIN_FACE_SIDE_PX = 40


def create_face_app(det_size: tuple[int, int] = DET_SIZE) -> FaceAnalysis:
    """Create the one model configuration used by indexing and search.

    The insightface package downloads model files to the user's home by
    default, which can fail on low-space system drives. Prefer a local
    project path or an explicit `INSIGHTFACE_ROOT` env var so the models
    are stored on the project's drive.
    """
    root = os.environ.get("INSIGHTFACE_ROOT")
    if not root:
        root = str(Path(__file__).parent.resolve() / ".insightface")
    app = FaceAnalysis(name=MODEL_NAME, root=root, providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=det_size)
    return app


def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    vector = embedding.astype("float32").reshape(1, -1)
    return vector / max(float(np.linalg.norm(vector)), 1e-12)


def face_size(face) -> tuple[float, float]:
    return float(face.bbox[2] - face.bbox[0]), float(face.bbox[3] - face.bbox[1])


def validate_single_face(faces) -> tuple[object | None, str | None]:
    """Return one usable face, or a safe user-facing reason to reject input."""
    if not faces:
        return None, "No face detected. Use a clear, front-facing reference image."
    if len(faces) > 1:
        return None, "More than one face detected. Upload an image containing only the intended person."
    face = faces[0]
    width, height = face_size(face)
    if min(width, height) < MIN_FACE_SIDE_PX:
        return None, f"Face is too small ({int(min(width, height))} px). Use a closer, sharper image."
    if float(face.det_score) < MIN_DETECTION_SCORE:
        return None, "Face detection quality is too low. Use a better-lit, less blurred image."
    return face, None
