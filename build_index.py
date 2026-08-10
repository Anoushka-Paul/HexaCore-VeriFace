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
from pathlib import Path

import cv2
import faiss
import numpy as np

from face_utils import create_face_app, normalize_embedding, validate_single_face


def parse_identity(label: str):
    """Splits 'personID_name' into (person_id, name)."""
    stem = os.path.splitext(label)[0]
    parts = stem.split("_", 1)
    person_id = parts[0]
    name = parts[1].replace("_", " ") if len(parts) > 1 else parts[0]
    return person_id, name


def identity_for_path(path: Path, input_path: Path) -> tuple[str, str]:
    """Support legacy flat files and preferred per-person reference folders.

    Preferred: dataset/001_Jane_Doe/reference_01.jpg
    Legacy:    dataset/001_Jane_Doe.jpg
    Flat multi-reference files may use: 001_Jane_Doe__02.jpg
    """
    if path.parent != input_path:
        return parse_identity(path.parent.name)
    return parse_identity(path.stem.split("__", 1)[0])


def build_index(input_dir: str, output_index: str, output_map: str):
    print("Loading insightface model...")
    app = create_face_app()

    embeddings = []
    mapping = []
    skipped = []
    canonical_ids_by_name = {}

    input_path = Path(input_dir)
    image_files = sorted(
        path for path in input_path.rglob("*")
        if path.is_file() and path.suffix.lower() in (".jpg", ".jpeg", ".png")
    )

    if not image_files:
        raise SystemExit(f"No images found in '{input_dir}'")

    print(f"Found {len(image_files)} images. Processing...")

    for path in image_files:
        relative_path = path.relative_to(input_path).as_posix()
        img = cv2.imread(str(path))

        if img is None:
            skipped.append((relative_path, "could not read image file"))
            continue

        face, reason = validate_single_face(app.get(img))
        if reason:
            skipped.append((relative_path, reason))
            continue

        embedding = normalize_embedding(face.embedding)[0]
        embeddings.append(embedding)

        source_person_id, name = identity_for_path(path, input_path)
        # The legacy LFW demo files assign a different sequential ID to every
        # image. Consolidate repeated names into one identity while retaining
        # each image as a separate FAISS reference vector.
        name_key = name.casefold()
        person_id = canonical_ids_by_name.setdefault(name_key, source_person_id)
        mapping.append({
            "person_id": person_id,
            "name": name,
            "filename": relative_path,
            "source_person_id": source_person_id,
        })

    if not embeddings:
        raise SystemExit("No embeddings were extracted — nothing to index.")

    embeddings = np.vstack(embeddings)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    faiss.write_index(index, output_index)
    with open(output_map, "w") as f:
        json.dump(mapping, f, indent=2)

    print(f"\nIndexed {len(mapping)} reference faces for {len({entry['person_id'] for entry in mapping})} people ({dim}-dim embeddings).")
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
