"""
pregenerate_cctv_demo.py

Safety net for the live demo's CCTV feature: pre-runs the existing
cctv_scan.run_cctv_scan() on one or more test videos AHEAD of time, and
saves the JSON results + evidence crops + review video to disk. If live
scanning is too slow/unstable during the actual demo, load these
pre-computed results instead.

This reuses your team's existing cctv_scan.py (run_cctv_scan) directly —
it does not reimplement CCTV scanning, since that's already built and
wired into main.py's /cctv-scan endpoint.

Usage:
    python pregenerate_cctv_demo.py \
        --video demo_assets/demo_cctv_simulated.mp4 \
        --target demo_assets/fictional_suspect_reference.jpg \
        --camera-id demo_corridor

    # Run on multiple test videos in one go:
    python pregenerate_cctv_demo.py \
        --video demo_assets/cam1.mp4 --target demo_assets/target.jpg --camera-id cam_1 \
        --also-video demo_assets/cam2.mp4 --also-camera-id cam_2
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

try:
    from cctv_scan import run_cctv_scan
except ImportError:
    sys.exit(
        "Could not import 'run_cctv_scan' from cctv_scan.py.\n"
        "This script must be run from inside the VeriFace repo root, "
        "next to the existing cctv_scan.py file."
    )

CACHE_DIR = os.path.join("demo_assets", "cctv_precomputed")
MANIFEST_PATH = os.path.join(CACHE_DIR, "manifest.json")


def run_one_job(video_path: str, target_path: str, camera_id: str, interval: float, threshold: float) -> dict:
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not os.path.isfile(target_path):
        raise FileNotFoundError(f"Target photo not found: {target_path}")

    job_dir = os.path.join(CACHE_DIR, camera_id)
    evidence_dir = os.path.join(job_dir, "evidence")
    review_video_path = os.path.join(job_dir, "review.mp4")
    os.makedirs(evidence_dir, exist_ok=True)

    print(f"Scanning '{video_path}' for camera '{camera_id}'...")
    results = run_cctv_scan(
        video_path, target_path, camera_id, interval, threshold,
        evidence_dir, review_video_path,
    )

    results_path = os.path.join(job_dir, "results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    return {
        "camera_id": camera_id,
        "video": video_path,
        "target": target_path,
        "results_json": results_path,
        "review_video": review_video_path,
        "evidence_dir": evidence_dir,
        "match_count": len(results.get("matches", [])),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="Pre-run CCTV scanning for demo-day fallback.")
    parser.add_argument("--video", required=True, help="Path to the primary test video")
    parser.add_argument("--target", required=True, help="Path to the target reference photo")
    parser.add_argument("--camera-id", default="cam_1", help="Camera ID label for the primary video")
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between sampled frames")
    parser.add_argument("--threshold", type=float, default=0.45, help="Similarity threshold for a match")
    parser.add_argument("--also-video", help="Optional: a second video to scan (simulating another camera)")
    parser.add_argument("--also-camera-id", default="cam_2", help="Camera ID for the second video")
    args = parser.parse_args()

    os.makedirs(CACHE_DIR, exist_ok=True)
    manifest = []

    jobs = [(args.video, args.target, args.camera_id)]
    if args.also_video:
        jobs.append((args.also_video, args.target, args.also_camera_id))

    for video_path, target_path, camera_id in jobs:
        try:
            entry = run_one_job(video_path, target_path, camera_id, args.interval, args.threshold)
            manifest.append(entry)
            print(f"  -> {entry['match_count']} match(es) cached for '{camera_id}'")
        except FileNotFoundError as e:
            print(f"  Skipped '{camera_id}': {e}", file=sys.stderr)

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nDone. {len(manifest)}/{len(jobs)} camera(s) pre-scanned.")
    print(f"Manifest saved to: {MANIFEST_PATH}")
    print("If live /cctv-scan is too slow/unstable during the demo, load these results.json files directly.")


if __name__ == "__main__":
    main()
