"""YOLOX person detector on cv2.dnn, with no frame retention.

The model is the OpenCV zoo object_detection_yolox_2022nov.onnx (COCO, 80 classes).
Get it with tools/get_person_model.py. Pre- and post-processing follow the zoo's
models/object_detection_yolox/demo.py and yolox.py: RGB, letterbox to 640x640 with
pad value 114, no normalisation, then grid and stride decoding of the raw output.
"""
from functools import lru_cache
import hashlib
from pathlib import Path

import cv2
import numpy

MODEL_PATH = Path(__file__).resolve().parent / "models" / "object_detection_yolox_2022nov.onnx"
MODEL_SHA256 = "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063"
INPUT_SIZE = (640, 640)  # (height, width)
STRIDES = (8, 16, 32)
NMS_THRESHOLD = 0.5
PERSON = 0


class ModelError(Exception):
    pass


def check_model(path: Path | None = None) -> None:
    """Raise ModelError when the model file is missing or its SHA-256 is not MODEL_SHA256."""
    path = Path(MODEL_PATH if path is None else path)
    hint = "Run: env/bin/python tools/get_person_model.py"
    if not path.is_file():
        raise ModelError(f"Person model not found at {path}. {hint}")
    digest = hashlib.sha256()
    with path.open("rb") as model_file:
        for chunk in iter(lambda: model_file.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != MODEL_SHA256:
        raise ModelError(f"Person model at {path} has the wrong SHA-256. {hint}")


@lru_cache(maxsize=4)
def _anchors(input_size):
    """Grid offsets (N, 2) and strides (N, 1) for every anchor, in the zoo's order."""
    grids, strides = [], []
    for stride in STRIDES:
        rows, cols = input_size[0] // stride, input_size[1] // stride
        xv, yv = numpy.meshgrid(numpy.arange(cols), numpy.arange(rows))
        grid = numpy.stack((xv, yv), 2).reshape(-1, 2)
        grids.append(grid)
        strides.append(numpy.full((len(grid), 1), stride))
    return numpy.concatenate(grids).astype(numpy.float32), numpy.concatenate(strides).astype(numpy.float32)


def _person_scores(raw_output):
    """Rows (N, 85) of a raw YOLOX output and the person score of each row: objectness x class-0 score."""
    dets = numpy.asarray(raw_output, numpy.float32).reshape(-1, 85)
    return dets, dets[:, 4] * dets[:, 5 + PERSON]


def person_boxes(raw_output, confidence: float, frame_shape, input_size) -> list:
    """Decode a raw YOLOX output and return person boxes [x, y, w, h] in frame pixels, after NMS.

    The person score is objectness x the class-0 score (YOLOX class scores are independent sigmoids).
    """
    dets, scores = _person_scores(raw_output)
    keep = scores >= confidence
    if not keep.any():
        return []
    grids, strides = _anchors(tuple(input_size))
    dets, scores, grids, strides = dets[keep], scores[keep], grids[keep], strides[keep]
    centres = (dets[:, :2] + grids) * strides
    sizes = numpy.exp(dets[:, 2:4]) * strides
    ratio = min(input_size[0] / frame_shape[0], input_size[1] / frame_shape[1])
    boxes = numpy.concatenate([centres - sizes / 2, sizes], axis=1) / ratio
    kept = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), confidence, NMS_THRESHOLD)
    return [boxes[i].tolist() for i in numpy.asarray(kept).reshape(-1)]


class PersonDetector:
    def __init__(self, confidence: float = 0.5, path: Path | None = None, net=None):
        self.confidence = confidence
        if net is None:
            path = Path(MODEL_PATH if path is None else path)
            check_model(path)
            net = cv2.dnn.readNet(str(path))
        self.net = net

    def detect(self, frame) -> bool:
        """True when at least one person is in the BGR frame. The frame is not kept."""
        return bool(person_boxes(self._forward(frame), self.confidence, frame.shape, INPUT_SIZE))

    def top_score(self, frame) -> float:
        """Highest person score in the BGR frame, before the threshold (0.0 with no candidate). For diagnostics."""
        scores = _person_scores(self._forward(frame))[1]
        return float(scores.max()) if scores.size else 0.0

    def _forward(self, frame):
        """Letterbox the BGR frame as the zoo does, run the net and return its raw output. The frame is not kept."""
        height, width = INPUT_SIZE
        ratio = min(height / frame.shape[0], width / frame.shape[1])
        new_w, new_h = int(frame.shape[1] * ratio), int(frame.shape[0] * ratio)
        padded = numpy.full((height, width, 3), 114.0, numpy.float32)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        padded[:new_h, :new_w] = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        self.net.setInput(numpy.transpose(padded, (2, 0, 1))[numpy.newaxis])
        return self.net.forward()
