"""Build a clearly-labelled simulated CCTV MP4 from a reference photo.

It is for pipeline testing only.  It intentionally models distance, compression,
motion blur, low light, and frame noise; it must never be represented as real
surveillance evidence.
"""

import argparse
from pathlib import Path

import cv2
import numpy as np


def paste_subject(frame, portrait, centre_x, baseline, scale):
    """Place a full-body RGBA subject; alpha avoids a pasted-photo rectangle."""
    portrait_h = max(24, int(portrait.shape[0] * scale))
    portrait_w = max(20, int(portrait.shape[1] * scale))
    subject = cv2.resize(portrait, (portrait_w, portrait_h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    # At close range the person naturally extends below the frame, but their
    # face remains visible near the camera's upper-middle field of view.
    x0 = int(centre_x - portrait_w / 2)
    y0 = max(0, int(baseline - portrait_h))
    dst_x0, dst_y0 = max(0, x0), max(0, y0)
    dst_x1, dst_y1 = min(frame.shape[1], x0 + portrait_w), min(frame.shape[0], y0 + portrait_h)
    if dst_x1 <= dst_x0 or dst_y1 <= dst_y0:
        return
    src_x0, src_y0 = dst_x0 - x0, dst_y0 - y0
    src_x1, src_y1 = src_x0 + (dst_x1 - dst_x0), src_y0 + (dst_y1 - dst_y0)
    subject = subject[src_y0:src_y1, src_x0:src_x1]
    roi = frame[dst_y0:dst_y1, dst_x0:dst_x1]
    alpha = subject[:, :, 3:4].astype(np.float32) / 255.0
    frame[dst_y0:dst_y1, dst_x0:dst_x1] = (subject[:, :, :3] * alpha + roi * (1 - alpha)).astype(np.uint8)


def cctv_degrade(frame, rng):
    small = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (3, 3), 0.65)
    noise = rng.normal(0, 5, small.shape).astype(np.int16)
    small = np.clip(small.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return cv2.resize(small, (1280, 720), interpolation=cv2.INTER_LINEAR)


def main():
    parser = argparse.ArgumentParser(description="Create a simulated CCTV MP4 for scanner testing.")
    parser.add_argument("--background", default="demo_assets/cctv_corridor_background.png")
    parser.add_argument("--portrait", default="demo_assets/fictional_subject.png", help="RGBA cutout of the fictional subject")
    parser.add_argument("--output", default="demo_cctv_simulated.mp4")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--fps", type=int, default=15)
    args = parser.parse_args()
    if args.seconds <= 0 or args.fps < 1:
        raise SystemExit("--seconds and --fps must be positive")
    background, portrait = cv2.imread(args.background), cv2.imread(args.portrait, cv2.IMREAD_UNCHANGED)
    if background is None or portrait is None:
        raise SystemExit("Could not read --background or --portrait")
    background = cv2.resize(background, (1280, 720), interpolation=cv2.INTER_AREA)
    writer = cv2.VideoWriter(args.output, cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (1280, 720))
    if not writer.isOpened():
        raise SystemExit(f"Could not create {args.output}")
    rng, total = np.random.default_rng(20260810), int(args.seconds * args.fps)
    for frame_number in range(total):
        progress = frame_number / max(1, total - 1)
        frame = background.copy()
        # The target enters distant, approaches the camera, pauses in the
        # useful recognition zone, then exits.  Scale is intentionally modest.
        if .12 <= progress <= .88:
            approach = min(1.0, max(0.0, (progress - .12) / .52))
            depart = max(0.0, (progress - .76) / .12)
            scale = .16 + .66 * approach * (1 - .55 * depart)
            x = int(710 - 260 * progress + 14 * np.sin(frame_number * .35))
            paste_subject(frame, portrait, x, 650, scale)
        frame = cctv_degrade(frame, rng)
        cv2.putText(frame, "SIMULATED CCTV - TEST FOOTAGE ONLY", (24, 42), cv2.FONT_HERSHEY_SIMPLEX, .72, (20, 30, 235), 2, cv2.LINE_AA)
        cv2.putText(frame, f"CAM DEMO-01   2026-08-10 10:00:{frame_number // args.fps:02d}", (24, 690), cv2.FONT_HERSHEY_SIMPLEX, .56, (235, 235, 235), 1, cv2.LINE_AA)
        writer.write(frame)
    writer.release()
    print(f"Created {Path(args.output).resolve()} ({total} frames at {args.fps} fps).")


if __name__ == "__main__":
    main()
