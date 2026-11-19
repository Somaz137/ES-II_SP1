#!/usr/bin/env python3
"""Download the YOLOX person model to models/ and check its pinned SHA-256.

Source: OpenCV zoo on Hugging Face (opencv/opencv_zoo), pinned to revision
d4938dfc9d4ec5d098bfa33e98b3f3345a236586:
https://huggingface.co/opencv/opencv_zoo/resolve/d4938dfc9d4ec5d098bfa33e98b3f3345a236586/models/object_detection_yolox/object_detection_yolox_2022nov.onnx
SHA-256: c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063 (35,858,002 bytes)
Licence: Apache License 2.0 (models/object_detection_yolox/LICENSE in the zoo).

The file is written to a temporary name, checked, then renamed. On a hash
mismatch the temporary file is deleted and the tool exits 1.
"""
import hashlib
import socket
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from person_detector import MODEL_PATH, MODEL_SHA256  # noqa: E402

URL = (
    "https://huggingface.co/opencv/opencv_zoo/resolve/d4938dfc9d4ec5d098bfa33e98b3f3345a236586/"
    "models/object_detection_yolox/object_detection_yolox_2022nov.onnx"
)


def _ipv4_only(getaddrinfo):
    # This host has no IPv6 route: resolve IPv4 addresses only.
    def resolve(host, port, family=0, *args, **kwargs):
        return getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)
    return resolve


def main():
    socket.getaddrinfo = _ipv4_only(socket.getaddrinfo)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = MODEL_PATH.with_name(MODEL_PATH.name + ".part")
    digest = hashlib.sha256()
    print(f"Downloading {URL}")
    try:
        with urllib.request.urlopen(URL, timeout=60) as response, temporary.open("wb") as out:
            for chunk in iter(lambda: response.read(1 << 20), b""):
                digest.update(chunk)
                out.write(chunk)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    if digest.hexdigest() != MODEL_SHA256:
        temporary.unlink(missing_ok=True)
        print(f"SHA-256 mismatch: got {digest.hexdigest()}, expected {MODEL_SHA256}", file=sys.stderr)
        return 1
    temporary.replace(MODEL_PATH)
    print(f"SHA-256 OK: {MODEL_SHA256}")
    print(f"Saved {MODEL_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
