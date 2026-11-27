"""Camera occupancy checks: one YOLOX person check per interval, no frame retention."""
from threading import Event, Lock, Thread
import time

from occupancy_rule import OccupancyRule


class CameraOccupancy:
    def __init__(self, index, timing, detector=None):
        self.index = index
        self.interval_s = timing["camera_interval_s"]
        self.confidence = timing["person_confidence"]
        self.rule = OccupancyRule(self.interval_s, timing["occupancy_confirm_s"],
                                  timing["occupancy_confirm_fraction"], timing["occupancy_hold_s"])
        self.detector = detector
        self.last_check_at = None
        self.lock = Lock()
        self.stop = Event()
        self.worker = Thread(target=self.run, daemon=True)

    def __enter__(self):
        self.worker.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.worker.join(timeout=1)

    def record(self, result, at):
        with self.lock:
            self.rule.add(result, at)
            self.last_check_at = at

    def assume_occupied(self, at):
        with self.lock:
            self.rule.assume_occupied(at)

    def snapshot(self, now):
        with self.lock:
            return self.rule.state(now)

    def check_once(self, open_capture, detector, at):
        """One check: grab a frame, classify it, release it. The frame is never kept."""
        import cv2

        result = "failed"
        capture = frame = None
        try:
            capture = open_capture(self.index)
            ok, frame = capture.read()
            if ok and frame is not None:
                result = "seen" if detector.detect(frame) else "not_seen"
        except cv2.error:
            pass
        finally:
            frame = None
            if capture is not None:
                capture.release()
        self.record(result, at)

    def run(self):
        import cv2
        from person_detector import PersonDetector

        detector = self.detector or PersonDetector(self.confidence)
        while not self.stop.is_set():
            started = time.monotonic()
            self.check_once(cv2.VideoCapture, detector, started)
            self.stop.wait(max(0, self.interval_s - (time.monotonic() - started)))
