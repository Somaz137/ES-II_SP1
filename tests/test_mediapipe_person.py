import importlib.util
from pathlib import Path

import numpy
import pytest

from person_detector import ModelError

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("mediapipe_person", ROOT / "src" / "tools" / "mediapipe_person.py")
mediapipe_person = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mediapipe_person)

ANCHORS = 2254


def raw_output(high_logit=3.0, low_logit=-10.0):
    """Zoo output layout: boxes+landmarks (1, N, 12) and score logits (1, N, 1); anchor 100 is high."""
    boxes = numpy.zeros((1, ANCHORS, 12), numpy.float32)
    boxes[0, :, 2:4] = 22.4  # a box 0.1 of the input wide and high
    scores = numpy.full((1, ANCHORS, 1), low_logit, numpy.float32)
    scores[0, 100, 0] = high_logit
    return [boxes, scores]


class StubNet:
    def __init__(self, outputs):
        self.outputs = outputs

    def setInput(self, blob):
        assert blob.shape == (1, 3, 224, 224)

    def getUnconnectedOutLayersNames(self):
        return ["boxes", "scores"]

    def forward(self, names=None):
        return self.outputs


def test_mp_missing_model_raises_with_download_hint(tmp_path):
    with pytest.raises(ModelError, match="src/tools/get_person_model.py"):
        mediapipe_person.MediaPipePerson(path=tmp_path / "missing.onnx")


def test_mp_postprocess_keeps_scores_above_threshold():
    frame_shape = (480, 640, 3)
    assert len(mediapipe_person.person_boxes(raw_output(), 0.5, frame_shape)) == 1
    assert mediapipe_person.person_boxes(raw_output(), 0.99, frame_shape) == []


def test_mp_detect_uses_stub_net():
    frame = numpy.zeros((480, 640, 3), numpy.uint8)
    assert mediapipe_person.MediaPipePerson(net=StubNet(raw_output())).detect(frame) is True
    assert mediapipe_person.MediaPipePerson(net=StubNet(raw_output(high_logit=-10.0))).detect(frame) is False


def test_mp_top_score_is_the_sigmoid_of_the_best_logit():
    frame = numpy.zeros((480, 640, 3), numpy.uint8)
    top = mediapipe_person.MediaPipePerson(net=StubNet(raw_output())).top_score(frame)
    assert top == pytest.approx(0.9526, abs=1e-3)


def test_production_modules_do_not_import_mediapipe():
    for name in ("occupancy.py", "monitor.py", "person_detector.py"):
        assert "mediapipe" not in (ROOT / "src" / name).read_text().lower(), name
