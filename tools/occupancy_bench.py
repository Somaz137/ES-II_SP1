#!/usr/bin/env python3
"""Compare HOG and YOLOX person detection on live webcam frames.

Usage: env/bin/python -I tools/occupancy_bench.py --camera 0 [--frames 12] [--confidence 0.5]

Each second it captures one frame (open, read, release, as occupancy.py does),
runs both detectors and prints one line with the mean pixel value and the
highest YOLOX person score before the threshold. No frame is written, sent or kept.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2  # noqa: E402
from person_detector import ModelError, PersonDetector  # noqa: E402


def capture_frame(index):
    capture = cv2.VideoCapture(index)
    try:
        ok, frame = capture.read()
        return frame if ok else None
    finally:
        capture.release()


def frame_line(i, hog_seen, yolox_seen, mean, top):
    """One bench line: the mean pixel value (0-255) shows a dark frame, top shows how close YOLOX came."""
    return (f"frame {i}: HOG {'yes' if hog_seen else 'no'} YOLOX {'yes' if yolox_seen else 'no'}"
            f" (mean {mean:.0f}, top {top:.2f})")


def totals_line(hog_hits, yolox_hits, frames, confidence):
    return f"HOG {hog_hits}/{frames}, YOLOX {yolox_hits}/{frames} at confidence {confidence:.2f}"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--camera", type=int, required=True, help="camera index, e.g. 0 for /dev/video0")
    parser.add_argument("--frames", type=int, default=12)
    parser.add_argument("--confidence", type=float, default=0.5, help="YOLOX threshold for the yes/no column")
    return parser.parse_args(argv)


def main():
    args = parse_args()

    try:
        yolox = PersonDetector(confidence=args.confidence)
    except ModelError as error:
        print(error, file=sys.stderr)
        return 1
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    hog_hits = yolox_hits = 0
    yolox_ms = []  # inference times only, never frames
    for i in range(1, args.frames + 1):
        started = time.monotonic()
        frame = capture_frame(args.camera)
        if frame is None or frame.shape[0] < 128 or frame.shape[1] < 64:
            print(f"frame {i}: capture failed")
        else:
            boxes, _ = hog.detectMultiScale(frame, winStride=(8, 8), scale=1.05)
            hog_seen = len(boxes) > 0
            yolox_started = time.perf_counter()
            yolox_seen = yolox.detect(frame)
            yolox_ms.append((time.perf_counter() - yolox_started) * 1000)
            top = yolox.top_score(frame)  # a second inference, for diagnostics; not timed
            hog_hits += hog_seen
            yolox_hits += yolox_seen
            print(frame_line(i, hog_seen, yolox_seen, float(frame.mean()), top), flush=True)
        frame = None
        if i < args.frames:
            time.sleep(max(0.0, 1.0 - (time.monotonic() - started)))

    print(totals_line(hog_hits, yolox_hits, args.frames, args.confidence))
    if yolox_ms:
        print(f"YOLOX {sum(yolox_ms) / len(yolox_ms):.0f} ms per frame (mean of {len(yolox_ms)}, fastest {min(yolox_ms):.0f} ms)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
