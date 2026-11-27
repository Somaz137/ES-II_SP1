#!/usr/bin/env python3
"""Compare HOG and YOLOX person detection on live webcam frames.

Usage: env/bin/python -I tools/occupancy_bench.py --camera 0 [--frames 12] [--confidence 0.5]

Each second it captures one frame (open, read, release, as occupancy.py does),
runs both detectors and prints one line with the mean pixel value and the
highest YOLOX person score before the threshold. When models/person_detection_mediapipe_2023mar.onnx
is present (tools/get_person_model.py --mediapipe), each line also shows the MediaPipe result and top score. No frame is written, sent or kept.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cv2  # noqa: E402
from mediapipe_person import MP_MODEL_PATH, MediaPipePerson  # noqa: E402
from person_detector import ModelError, PersonDetector  # noqa: E402


def capture_frame(index):
    capture = cv2.VideoCapture(index)
    try:
        ok, frame = capture.read()
        return frame if ok else None
    finally:
        capture.release()


def frame_line(i, hog_seen, yolox_seen, mean, top, mp=None):
    """One bench line: the mean pixel value (0-255) shows a dark frame, top shows how close YOLOX came.

    mp is None or (seen, top score) of MediaPipe. Scores have 3 decimals, so a score just under the threshold shows as under it.
    """
    line = (f"frame {i}: HOG {'yes' if hog_seen else 'no'} YOLOX {'yes' if yolox_seen else 'no'}"
            f" (mean {mean:.0f}, top {top:.3f})")
    if mp is not None:
        line += f" MP {'yes' if mp[0] else 'no'} (top {mp[1]:.3f})"
    return line


def totals_line(hog_hits, yolox_hits, frames, confidence, mp_hits=None):
    mp = "" if mp_hits is None else f", MP {mp_hits}/{frames}"
    return f"HOG {hog_hits}/{frames}, YOLOX {yolox_hits}/{frames}{mp} at confidence {confidence:.2f}"


def load_mediapipe(confidence):
    """The MediaPipe detector, or None (after one note) when its model file is missing."""
    if not MP_MODEL_PATH.is_file():
        print("Note: MediaPipe model not found, so there is no MP column. Run: env/bin/python tools/get_person_model.py --mediapipe")
        return None
    try:
        return MediaPipePerson(confidence=confidence)
    except ModelError as error:
        print(f"Note: {error} There is no MP column.")
        return None


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
    mediapipe = load_mediapipe(args.confidence)
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    hog_hits = yolox_hits = mp_hits = 0
    yolox_ms, mp_ms = [], []  # inference times only, never frames
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
            mp = None
            if mediapipe is not None:
                mp_started = time.perf_counter()
                mp_seen = mediapipe.detect(frame)
                mp_ms.append((time.perf_counter() - mp_started) * 1000)
                mp = (mp_seen, mediapipe.top_score(frame))
                mp_hits += mp_seen
            hog_hits += hog_seen
            yolox_hits += yolox_seen
            print(frame_line(i, hog_seen, yolox_seen, float(frame.mean()), top, mp), flush=True)
        frame = None
        if i < args.frames:
            time.sleep(max(0.0, 1.0 - (time.monotonic() - started)))

    print(totals_line(hog_hits, yolox_hits, args.frames, args.confidence, mp_hits if mediapipe is not None else None))
    if yolox_ms:
        print(f"YOLOX {sum(yolox_ms) / len(yolox_ms):.0f} ms per frame (mean of {len(yolox_ms)}, fastest {min(yolox_ms):.0f} ms)")
    if mp_ms:
        print(f"MP {sum(mp_ms) / len(mp_ms):.0f} ms per frame (mean of {len(mp_ms)}, fastest {min(mp_ms):.0f} ms)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
