"""CCTV candidate-review scanner.

This is deliberately a *candidate* generator, not an identification system.  It
uses a full-frame pass plus overlapping, enlarged tiles so a face which is too
small in a wide CCTV shot gets another chance to be detected.  Matches are
saved with crops and an annotated MP4 so an operator can review the evidence.

Example:
    python cctv_scan.py --video demo_cctv.mp4 --target suspect.jpg \
        --camera-id demo_corridor --interval 0.25 --annotated-video review.mp4
"""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from face_utils import create_face_app, normalize_embedding


def confidence_label(similarity: float) -> str:
    """Conservative review labels; never treat a score as a confirmed identity."""
    if similarity >= 0.75:
        return "review priority"
    if similarity >= 0.50:
        return "possible candidate"
    return "low-score candidate"


def area(box: np.ndarray) -> float:
    return max(0.0, float(box[2] - box[0])) * max(0.0, float(box[3] - box[1]))


def iou(a: np.ndarray, b: np.ndarray) -> float:
    left, top = max(a[0], b[0]), max(a[1], b[1])
    right, bottom = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, right - left) * max(0.0, bottom - top)
    return inter / max(area(a) + area(b) - inter, 1e-12)


def enhance(frame: np.ndarray) -> np.ndarray:
    """Mild local contrast correction; it does not invent facial detail."""
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def full_and_tile_faces(face_app, frame: np.ndarray, tile_scan: bool) -> list[tuple]:
    """Return (face, original-frame bbox, source) with duplicate detections removed."""
    work = enhance(frame)
    found: list[tuple] = [(face, face.bbox.astype(float), "full_frame") for face in face_app.get(work)]
    if not tile_scan:
        return found

    height, width = work.shape[:2]
    # Four overlapping regions. Enlarging a local crop is useful for a small
    # face in a 720p/1080p wide shot without requiring a new detector package.
    x_edges = [(0, int(width * 0.60)), (int(width * 0.40), width)]
    y_edges = [(0, int(height * 0.60)), (int(height * 0.40), height)]
    for y0, y1 in y_edges:
        for x0, x1 in x_edges:
            crop = work[y0:y1, x0:x1]
            enlarged = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            for face in face_app.get(enlarged):
                box = face.bbox.astype(float) / 2.0
                box[[0, 2]] += x0
                box[[1, 3]] += y0
                if not any(iou(box, known_box) >= 0.45 for _, known_box, _ in found):
                    found.append((face, box, "upscaled_tile"))
    return found


def get_target_embedding(face_app, target_path: str) -> np.ndarray:
    img = cv2.imread(target_path)
    if img is None:
        raise SystemExit(f"Could not read target image: {target_path}")
    faces = face_app.get(enhance(img))
    if not faces:
        raise SystemExit(f"No face detected in target image: {target_path}")
    return normalize_embedding(max(faces, key=lambda f: area(f.bbox)).embedding)


def clip_box(box: np.ndarray, frame: np.ndarray) -> tuple[int, int, int, int]:
    height, width = frame.shape[:2]
    x0, y0, x1, y1 = map(int, np.round(box))
    return max(0, x0), max(0, y0), min(width, x1), min(height, y1)


def draw_candidate(frame: np.ndarray, match: dict) -> None:
    x0, y0, x1, y1 = match["bbox"]
    color = (0, 190, 255) if match["similarity"] >= 0.75 else (0, 220, 220)
    cv2.rectangle(frame, (x0, y0), (x1, y1), color, 2)
    label = f"CANDIDATE {match['similarity']:.2f} | human review"
    cv2.putText(frame, label, (x0, max(22, y0 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.52, color, 2, cv2.LINE_AA)


def save_crop(frame: np.ndarray, match: dict, evidence_dir: Path) -> str:
    x0, y0, x1, y1 = match["bbox"]
    pad = int(max(x1 - x0, y1 - y0) * 0.25)
    crop = frame[max(0, y0 - pad):min(frame.shape[0], y1 + pad), max(0, x0 - pad):min(frame.shape[1], x1 + pad)]
    filename = f"candidate_f{match['frame_number']:06d}_s{match['similarity']:.3f}.jpg"
    cv2.imwrite(str(evidence_dir / filename), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return filename


def group_events(matches: list[dict], max_gap_seconds: float) -> list[dict]:
    events: list[dict] = []
    for match in matches:
        if not events or match["timestamp_sec"] - events[-1]["end_sec"] > max_gap_seconds:
            events.append({"start_sec": match["timestamp_sec"], "end_sec": match["timestamp_sec"], "candidates": [match]})
        else:
            events[-1]["end_sec"] = match["timestamp_sec"]
            events[-1]["candidates"].append(match)
    for event in events:
        best = max(event.pop("candidates"), key=lambda item: item["similarity"])
        event.update({"best_similarity": best["similarity"], "best_frame": best["frame_number"], "evidence_image": best["evidence_image"], "review_status": "requires human verification"})
    return events


def scan_video(video_path: str, target_embedding: np.ndarray, face_app, args):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_interval = max(1, int(round(fps * args.interval)))
    evidence_dir = Path(args.evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    writer = None
    if args.annotated_video:
        writer = cv2.VideoWriter(args.annotated_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            raise SystemExit(f"Could not write annotated video: {args.annotated_video}")

    matches, sampled_frames, detected_faces, frame_number = [], 0, 0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        display = frame.copy()
        if frame_number % frame_interval == 0:
            sampled_frames += 1
            for face, box, source in full_and_tile_faces(face_app, frame, args.tile_scan):
                detected_faces += 1
                embedding = normalize_embedding(face.embedding)
                similarity = float(np.dot(embedding, target_embedding.T)[0, 0])
                if similarity < args.threshold:
                    continue
                x0, y0, x1, y1 = clip_box(box, frame)
                if x1 <= x0 or y1 <= y0:
                    continue
                match = {"timestamp_sec": round(frame_number / fps, 2), "frame_number": frame_number, "camera_id": args.camera_id, "similarity": round(similarity, 4), "confidence": confidence_label(similarity), "review_status": "requires human verification", "bbox": [x0, y0, x1, y1], "face_size_px": [x1 - x0, y1 - y0], "detection_source": source}
                match["evidence_image"] = save_crop(frame, match, evidence_dir)
                matches.append(match)
                draw_candidate(display, match)
        if writer:
            cv2.putText(display, f"CAM {args.camera_id}  FRAME {frame_number}", (18, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (240, 240, 240), 2, cv2.LINE_AA)
            writer.write(display)
        frame_number += 1
    cap.release()
    if writer:
        writer.release()
    return matches, {"frames_read": frame_number, "frames_sampled": sampled_frames, "faces_detected": detected_faces, "fps": fps, "resolution": [width, height], "tile_scan": args.tile_scan}


def run_cctv_scan(video_path: str, target_path: str, camera_id: str, interval: float,
                  threshold: float, evidence_dir: str, annotated_video: str,
                  det_size: int = 640, tile_scan: bool = True) -> dict:
    """Reusable scanner entrypoint for the CLI and FastAPI upload endpoint."""
    if interval <= 0 or det_size < 160:
        raise ValueError("interval must be positive and det_size must be at least 160")
    options = SimpleNamespace(
        camera_id=camera_id, interval=interval, threshold=threshold,
        evidence_dir=evidence_dir, annotated_video=annotated_video, tile_scan=tile_scan,
    )
    face_app = create_face_app((det_size, det_size))
    target_embedding = get_target_embedding(face_app, target_path)
    matches, stats = scan_video(video_path, target_embedding, face_app, options)
    return {
        "schema_version": "2.0",
        "disclaimer": "Candidate matches require human verification; this output does not establish identity.",
        "input": {"video": video_path, "camera_id": camera_id, "threshold": threshold},
        "statistics": stats,
        "matches": matches,
        "events": group_events(matches, max(interval * 2.5, 1.0)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate face-match candidates from recorded CCTV for human review.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--target", required=True, help="Clear, consented reference photo")
    parser.add_argument("--camera-id", default="cam_1")
    parser.add_argument("--interval", type=float, default=0.25, help="Seconds between analysed frames")
    parser.add_argument("--threshold", type=float, default=0.50)
    parser.add_argument("--det-size", type=int, default=640, help="InsightFace detector square size")
    parser.add_argument("--tile-scan", action=argparse.BooleanOptionalAction, default=True, help="Enable overlapping 2x enlarged crops")
    parser.add_argument("--output", default="cctv_results.json")
    parser.add_argument("--evidence-dir", default="cctv_evidence")
    parser.add_argument("--annotated-video", default="cctv_review.mp4")
    args = parser.parse_args()
    print(f"Scanning {args.video}; every {args.interval}s; tiled recovery: {args.tile_scan}")
    try:
        results = run_cctv_scan(
            args.video, args.target, args.camera_id, args.interval, args.threshold,
            args.evidence_dir, args.annotated_video, args.det_size, args.tile_scan,
        )
    except (SystemExit, ValueError) as error:
        raise SystemExit(str(error)) from error
    with open(args.output, "w", encoding="utf-8") as output_file:
        json.dump(results, output_file, indent=2)
    print(f"Scanned {results['statistics']['frames_read']} frames; {len(results['matches'])} candidate frame(s), {len(results['events'])} event(s).")
    print(f"Results: {args.output} | evidence: {args.evidence_dir} | review video: {args.annotated_video}")


if __name__ == "__main__":
    main()
