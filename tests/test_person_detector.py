import numpy
import pytest

import person_detector
from person_detector import ModelError, PersonDetector, check_model, person_boxes

INPUT_SIZE = (640, 640)
ROWS = (640 // 8) ** 2 + (640 // 16) ** 2 + (640 // 32) ** 2  # 8400 anchors
STRIDE_32_START = (640 // 8) ** 2 + (640 // 16) ** 2  # first stride-32 anchor
DOG = 16


def raw_output(*detections):
    """Build a raw YOLOX output (1, 8400, 85): per anchor dx, dy, log w, log h, objectness, 80 class scores.

    Each detection is (anchor_row, class_id, score, log_size). Objectness is 1.0, so the score is the class score.
    """
    out = numpy.zeros((1, ROWS, 85), numpy.float32)
    for row, class_id, score, log_size in detections:
        out[0, row, 2:4] = log_size
        out[0, row, 4] = 1.0
        out[0, row, 5 + class_id] = score
    return out


PERSON_09 = (STRIDE_32_START + 5 * 20 + 5, 0, 0.9, 1.5)
PERSON_03 = (STRIDE_32_START + 12 * 20 + 12, 0, 0.3, 1.5)
DOG_095 = (STRIDE_32_START + 2 * 20 + 15, DOG, 0.95, 1.5)


def test_missing_model_raises_with_download_hint(tmp_path):
    with pytest.raises(ModelError) as error:
        check_model(tmp_path / "x.onnx")
    assert "tools/get_person_model.py" in str(error.value)


def test_wrong_hash_raises(tmp_path):
    path = tmp_path / "x.onnx"
    path.write_bytes(b"not a model")
    with pytest.raises(ModelError) as error:
        check_model(path)
    assert "tools/get_person_model.py" in str(error.value)


def test_check_model_default_path_is_resolved_at_call_time(tmp_path, monkeypatch):
    monkeypatch.setattr(person_detector, "MODEL_PATH", tmp_path / "missing.onnx")
    with pytest.raises(ModelError) as error:
        check_model()
    assert "missing.onnx" in str(error.value)


def test_person_boxes_keeps_only_class_zero_above_threshold():
    boxes = person_boxes(raw_output(PERSON_09, PERSON_03, DOG_095), 0.5, (480, 640, 3), INPUT_SIZE)
    assert len(boxes) == 1


def test_overlapping_person_boxes_are_merged():
    # Two neighbouring stride-32 anchors with large boxes (exp(3) * 32 ~ 643 px): IoU is far above 0.5.
    first = (STRIDE_32_START + 10 * 20 + 10, 0, 0.9, 3.0)
    second = (STRIDE_32_START + 10 * 20 + 11, 0, 0.8, 3.0)
    assert len(person_boxes(raw_output(first, second), 0.5, (480, 640, 3), INPUT_SIZE)) == 1


def test_separate_person_boxes_are_both_kept():
    first = (STRIDE_32_START + 2 * 20 + 2, 0, 0.9, 1.0)
    second = (STRIDE_32_START + 15 * 20 + 15, 0, 0.8, 1.0)
    assert len(person_boxes(raw_output(first, second), 0.5, (480, 640, 3), INPUT_SIZE)) == 2


class StubNet:
    def __init__(self, output):
        self.output = output
        self.blob_shape = None

    def setInput(self, blob):
        self.blob_shape = blob.shape

    def forward(self):
        return self.output.copy()


def test_detect_uses_stub_net():
    frame = numpy.zeros((480, 640, 3), numpy.uint8)
    person_net = StubNet(raw_output(PERSON_09))
    assert PersonDetector(net=person_net).detect(frame) is True
    assert person_net.blob_shape == (1, 3, 640, 640)
    assert PersonDetector(net=StubNet(raw_output(DOG_095))).detect(frame) is False


def test_detector_keeps_no_frame():
    frame = numpy.zeros((480, 640, 3), numpy.uint8)
    detector = PersonDetector(net=StubNet(raw_output(PERSON_09)))
    detector.detect(frame)
    assert not any(isinstance(value, numpy.ndarray) for value in vars(detector).values())


def test_detector_without_net_checks_model_first(tmp_path):
    with pytest.raises(ModelError):
        PersonDetector(path=tmp_path / "x.onnx")
