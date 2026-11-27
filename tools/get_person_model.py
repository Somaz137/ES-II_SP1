#!/usr/bin/env python3
"""Download the YOLOX person model to models/ and check its pinned SHA-256.
With --mediapipe, download the MediaPipe person model instead (bench comparison only).

Source: OpenCV zoo on Hugging Face (opencv/opencv_zoo), pinned to revision
d4938dfc9d4ec5d098bfa33e98b3f3345a236586:
https://huggingface.co/opencv/opencv_zoo/resolve/d4938dfc9d4ec5d098bfa33e98b3f3345a236586/models/object_detection_yolox/object_detection_yolox_2022nov.onnx
SHA-256: c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063 (35,858,002 bytes)
Licence: Apache License 2.0 (models/object_detection_yolox/LICENSE in the zoo).

MediaPipe (--mediapipe), same revision:
https://huggingface.co/opencv/opencv_zoo/resolve/d4938dfc9d4ec5d098bfa33e98b3f3345a236586/models/person_detection_mediapipe/person_detection_mediapipe_2023mar.onnx
SHA-256: 47fd5599d6fa17608f03e0eb0ae230baa6e597d7e8a2c8199fe00abea55a701f (11,990,159 bytes)
Licence: Apache License 2.0 (models/person_detection_mediapipe/LICENSE in the zoo).

The file is written to a temporary name, checked, then renamed. On a hash
mismatch the temporary file is deleted and the tool exits 1.
"""
import argparse
import hashlib
import socket
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from person_detector import MODEL_PATH, MODEL_SHA256  # noqa: E402
from mediapipe_person import MP_MODEL_PATH, MP_MODEL_SHA256  # noqa: E402

URL = (
    "https://huggingface.co/opencv/opencv_zoo/resolve/d4938dfc9d4ec5d098bfa33e98b3f3345a236586/"
    "models/object_detection_yolox/object_detection_yolox_2022nov.onnx"
)
MP_URL = (
    "https://huggingface.co/opencv/opencv_zoo/resolve/d4938dfc9d4ec5d098bfa33e98b3f3345a236586/"
    "models/person_detection_mediapipe/person_detection_mediapipe_2023mar.onnx"
)


def _ipv4_only(getaddrinfo):
    # This host has no IPv6 route: resolve IPv4 addresses only.
    def resolve(host, port, family=0, *args, **kwargs):
        return getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)
    return resolve


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mediapipe", action="store_true", help="fetch the MediaPipe model (bench comparison only)")
    if parser.parse_args(argv).mediapipe:
        return download(MP_URL, MP_MODEL_PATH, MP_MODEL_SHA256)
    return download(URL, MODEL_PATH, MODEL_SHA256)


def download(url, model_path, model_sha256):
    socket.getaddrinfo = _ipv4_only(socket.getaddrinfo)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = model_path.with_name(model_path.name + ".part")
    digest = hashlib.sha256()
    print(f"Downloading {url}")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as out:
            for chunk in iter(lambda: response.read(1 << 20), b""):
                digest.update(chunk)
                out.write(chunk)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    if digest.hexdigest() != model_sha256:
        temporary.unlink(missing_ok=True)
        print(f"SHA-256 mismatch: got {digest.hexdigest()}, expected {model_sha256}", file=sys.stderr)
        return 1
    temporary.replace(model_path)
    print(f"SHA-256 OK: {model_sha256}")
    print(f"Saved {model_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
