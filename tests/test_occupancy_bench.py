import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "occupancy_bench", Path(__file__).resolve().parent.parent / "src" / "tools" / "occupancy_bench.py")
occupancy_bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(occupancy_bench)


def test_frame_line_shows_both_results_mean_brightness_and_top_score():
    assert occupancy_bench.frame_line(3, False, True, 92.4, 0.4712) == "frame 3: HOG no YOLOX yes (mean 92, top 0.471)"


def test_frame_line_shows_a_dark_frame_with_no_candidate():
    assert occupancy_bench.frame_line(1, True, False, 0.7, 0.0) == "frame 1: HOG yes YOLOX no (mean 1, top 0.000)"


def test_frame_line_adds_the_mediapipe_column_with_three_decimals():
    line = occupancy_bench.frame_line(2, False, False, 90.0, 0.4994, mp=(False, 0.4994))
    assert line == "frame 2: HOG no YOLOX no (mean 90, top 0.499) MP no (top 0.499)"
    assert occupancy_bench.frame_line(2, False, False, 90.0, 0.1, mp=(True, 0.9526)).endswith(" MP yes (top 0.953)")


def test_totals_line_adds_mediapipe_hits():
    assert occupancy_bench.totals_line(0, 4, 12, 0.5, mp_hits=3) == "HOG 0/12, YOLOX 4/12, MP 3/12 at confidence 0.50"


def test_totals_line_names_the_threshold():
    assert occupancy_bench.totals_line(0, 4, 12, 0.5) == "HOG 0/12, YOLOX 4/12 at confidence 0.50"


def test_confidence_option_defaults_to_half_and_is_passed_through():
    assert occupancy_bench.parse_args(["--camera", "0"]).confidence == 0.5
    args = occupancy_bench.parse_args(["--camera", "0", "--confidence", "0.3"])
    assert args.confidence == 0.3


def test_bench_builds_the_detector_with_the_chosen_confidence(monkeypatch):
    seen = {}

    class FakeDetector:
        def __init__(self, confidence):
            seen["confidence"] = confidence

    monkeypatch.setattr(occupancy_bench, "PersonDetector", FakeDetector)
    monkeypatch.setattr(occupancy_bench, "load_mediapipe", lambda confidence: None)
    monkeypatch.setattr(occupancy_bench.sys, "argv", ["occupancy_bench.py", "--camera", "0", "--frames", "0", "--confidence", "0.3"])
    assert occupancy_bench.main() == 0
    assert seen["confidence"] == 0.3
