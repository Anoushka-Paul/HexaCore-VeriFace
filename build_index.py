"""
build_index.py

Builds a searchable FAISS index from a folder of face images.

Expected input folder structure:
    dataset/
        001_john_doe.jpg
        002_jane_smith.jpg
        ...
    (filename format: <personID>_<name>.jpg — underscore-separated,
     everything after the first underscore is treated as the name)

Outputs:
    face_index.faiss   - the FAISS index (embeddings only)
    face_mapping.json  - list mapping FAISS index position -> {person_id, name, filename}

Usage:
    python build_index.py --input dataset --output_index face_index.faiss --output_map face_mapping.json
"""

import argparse
import json
import os

import cv2
import faiss
import numpy as np
from insightface.app import FaceAnalysis


def parse_filename(filename: str):
    """Splits 'personID_name.jpg' into (person_id, name)."""
    stem = os.path.splitext(filename)[0]
    parts = stem.split("_", 1)
    person_id = parts[0]
    name = parts[1].replace("_", " ") if len(parts) > 1 else parts[0]
    return person_id, name


def build_index(input_dir: str, output_index: str, output_map: str):
    print("Loading insightface model...")
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(160, 160))

    embeddings = []
    mapping = []
    skipped = []

    image_files = sorted(
        f for f in os.listdir(input_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )

    if not image_files:
        raise SystemExit(f"No images found in '{input_dir}'")

    print(f"Found {len(image_files)} images. Processing...")

    for filename in image_files:
        path = os.path.join(input_dir, filename)
        img = cv2.imread(path)

        if img is None:
            skipped.append((filename, "could not read image file"))
            continue

        faces = app.get(img)

        if len(faces) == 0:
            skipped.append((filename, "no face detected"))
            continue

        # If multiple faces are found in a reference image, use the
        # largest one (most likely the intended subject).
        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

        embedding = face.embedding.astype("float32")
        embeddings.append(embedding)

        person_id, name = parse_filename(filename)
        mapping.append({"person_id": person_id, "name": name, "filename": filename})

    if not embeddings:
        raise SystemExit("No embeddings were extracted — nothing to index.")

    embeddings = np.vstack(embeddings)

    # Normalize so IndexFlatIP (inner product) behaves like cosine similarity
    faiss.normalize_L2(embeddings)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    faiss.write_index(index, output_index)
    with open(output_map, "w") as f:
        json.dump(mapping, f, indent=2)

    print(f"\nIndexed {len(mapping)} faces ({dim}-dim embeddings).")
    print(f"Saved index -> {output_index}")
    print(f"Saved mapping -> {output_map}")

    if skipped:
        print(f"\nSkipped {len(skipped)} file(s):")
        for filename, reason in skipped:
            print(f"  - {filename}: {reason}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="dataset", help="Folder of face images")
    parser.add_argument("--output_index", default="face_index.faiss")
    parser.add_argument("--output_map", default="face_mapping.json")
    args = parser.parse_args()

    build_index(args.input, args.output_index, args.output_map)