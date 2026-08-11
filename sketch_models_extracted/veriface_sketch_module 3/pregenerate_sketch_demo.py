"""
pregenerate_sketch_demo.py

Safety net for the live demo: pre-runs sketch_to_photo.py on a folder of
known test sketches AHEAD of time, and caches the results + a manifest.
If the live model is flaky/slow during the actual demo, the frontend (or
you manually) can fall back to these guaranteed-working pre-converted
images instead of calling the live pipeline.

Usage:
    # 1. Put 2-3 sample sketches in demo_assets/sketch_samples/input/
    # 2. Run this once, ahead of the demo:
    python pregenerate_sketch_demo.py

    # Optional: point at a different folder
    python pregenerate_sketch_demo.py --input-dir some/other/folder --output-dir some/other/output
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from sketch_to_photo import convert_sketch_to_photo

DEFAULT_INPUT_DIR = os.path.join("demo_assets", "sketch_samples", "input")
DEFAULT_OUTPUT_DIR = os.path.join("demo_assets", "sketch_samples", "cached_output")
MANIFEST_PATH = os.path.join("demo_assets", "sketch_samples", "manifest.json")
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def find_sketch_files(input_dir: str) -> list[str]:
    if not os.path.isdir(input_dir):
        return []
    return sorted(
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
    )


def main():
    parser = argparse.ArgumentParser(description="Pre-generate cached sketch->photo demo results.")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR, help="Folder of sample sketches")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Where to save converted photos")
    parser.add_argument("--style", default="cufs", choices=["cufs", "cufsf"])
    args = parser.parse_args()

    sketch_paths = find_sketch_files(args.input_dir)
    if not sketch_paths:
        print(
            f"No sketch images found in '{args.input_dir}'.\n"
            f"Add 2-3 sample sketches there first (jpg/png/bmp), then re-run this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    manifest = []

    for sketch_path in sketch_paths:
        filename = os.path.basename(sketch_path)
        output_path = os.path.join(args.output_dir, filename)
        print(f"Converting {filename}...")
        try:
            convert_sketch_to_photo(sketch_path, output_path, style=args.style)
        except Exception as e:
            print(f"  Skipped {filename}: {e}", file=sys.stderr)
            continue

        manifest.append({
            "sketch_input": sketch_path,
            "cached_photo_output": output_path,
            "style": args.style,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nDone. {len(manifest)}/{len(sketch_paths)} sketches cached.")
    print(f"Manifest saved to: {MANIFEST_PATH}")
    print("If the live model has issues during the demo, use the cached_photo_output paths directly.")


if __name__ == "__main__":
    main()
