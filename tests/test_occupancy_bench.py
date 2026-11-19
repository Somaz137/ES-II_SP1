import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "occupancy_bench", Path(__file__).resolve().parent.parent / "tools" / "occupancy_bench.py")
occupancy_bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(occupancy_bench)


def test_frame_line_shows_both_results_and_mean_brightness():
    assert occupancy_bench.frame_line(3, False, True, 92.4) == "frame 3: HOG no YOLOX yes (mean 92)"


def test_frame_line_shows_a_dark_frame():
    assert occupancy_bench.frame_line(1, True, False, 0.7) == "frame 1: HOG yes YOLOX no (mean 1)"
