"""MediaPipe person detector on cv2.dnn, for the occupancy bench only (no production module imports it).

The model is the OpenCV zoo person_detection_mediapipe_2023mar.onnx. Get it with
tools/get_person_model.py --mediapipe. Pre- and post-processing follow the zoo's
models/person_detection_mediapipe/mp_persondet.py: RGB, scale to [-1, 1], letterbox
to 224x224 with black padding, sigmoid scores and anchor-relative box decoding.
"""
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import cv2  # noqa: E402
import numpy  # noqa: E402
from person_detector import ModelError, check_model  # noqa: E402,F401

MP_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "person_detection_mediapipe_2023mar.onnx"
MP_MODEL_SHA256 = "47fd5599d6fa17608f03e0eb0ae230baa6e597d7e8a2c8199fe00abea55a701f"
INPUT_SIZE = 224
NMS_THRESHOLD = 0.3  # the zoo's default
# (grid size, anchors per cell) of the zoo's 2254 anchors, in output order
ANCHOR_GRIDS = ((28, 2), (14, 2), (7, 6))


@lru_cache(maxsize=1)
def _anchors():
    """Anchor centres (2254, 2) as fractions of the padded input; they equal the zoo's table."""
    centres = []
    for size, per_cell in ANCHOR_GRIDS:
        for y in range(size):
            for x in range(size):
                centres.extend([((x + 0.5) / size, (y + 0.5) / size)] * per_cell)
    return numpy.array(centres, numpy.float64)


def _scores(raw_output):
    """Sigmoid of the score logits (N,) from the zoo's two outputs [boxes (1,N,12), scores (1,N,1)]."""
    logits = numpy.clip(numpy.asarray(raw_output[1], numpy.float64)[0, :, 0], -100, 100)
    return 1 / (1 + numpy.exp(-logits))


def person_boxes(raw_output, confidence: float, frame_shape) -> list:
    """Decode the raw outputs and return person boxes [x, y, w, h] in frame pixels, after NMS."""
    scores = _scores(raw_output)
    keep = scores >= confidence
    if not keep.any():
        return []
    deltas = numpy.asarray(raw_output[0], numpy.float64)[0, :, :4][keep] / INPUT_SIZE
    anchors = _anchors()[keep]
    scale = max(frame_shape[0], frame_shape[1])
    ratio = INPUT_SIZE / scale
    # the zoo's pad bias: the letterbox offset of the resized frame, in frame pixels
    pad = numpy.array([(INPUT_SIZE - int(frame_shape[1] * ratio)) // 2,
                       (INPUT_SIZE - int(frame_shape[0] * ratio)) // 2]) / ratio
    pad = pad.astype(numpy.int32)
    xy1 = (deltas[:, :2] - deltas[:, 2:] / 2 + anchors) * scale - pad
    wh = deltas[:, 2:] * scale
    boxes = numpy.concatenate([xy1, wh], axis=1)
    kept = cv2.dnn.NMSBoxes(boxes.tolist(), scores[keep].tolist(), confidence, NMS_THRESHOLD)
    return [boxes[i].tolist() for i in numpy.asarray(kept).reshape(-1)]


class MediaPipePerson:
    def __init__(self, confidence: float = 0.5, path: Path | None = None, net=None):
        self.confidence = confidence
        if net is None:
            path = Path(MP_MODEL_PATH if path is None else path)
            check_model(path, MP_MODEL_SHA256, "Run: env/bin/python tools/get_person_model.py --mediapipe")
            net = cv2.dnn.readNet(str(path))
        self.net = net

    def detect(self, frame) -> bool:
        """True when at least one person is in the BGR frame. The frame is not kept."""
        return bool(person_boxes(self._forward(frame), self.confidence, frame.shape))

    def top_score(self, frame) -> float:
        """Highest person score in the BGR frame, before the threshold. For diagnostics."""
        scores = _scores(self._forward(frame))
        return float(scores.max()) if scores.size else 0.0

    def _forward(self, frame):
        """Letterbox the BGR frame as the zoo does, run the net and return its raw outputs. The frame is not kept."""
        ratio = INPUT_SIZE / max(frame.shape[:2])
        new_h, new_w = int(frame.shape[0] * ratio), int(frame.shape[1] * ratio)
        rgb = (cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(numpy.float32) / 255.0 - 0.5) * 2
        pad_h, pad_w = INPUT_SIZE - new_h, INPUT_SIZE - new_w
        padded = cv2.copyMakeBorder(cv2.resize(rgb, (new_w, new_h)), pad_h // 2, pad_h - pad_h // 2,
                                    pad_w // 2, pad_w - pad_w // 2, cv2.BORDER_CONSTANT, None, (0, 0, 0))
        self.net.setInput(numpy.transpose(padded, (2, 0, 1))[numpy.newaxis])
        return self.net.forward(self.net.getUnconnectedOutLayersNames())
