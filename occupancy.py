"""Camera occupancy checks: one YOLOX person check per interval, no frame retention."""
import sys
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
        self.last_error = None
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

    def snapshot(self, now, wall=None):
        """The rule state. With `wall` (clock time of `now`), the times are clock times, not monotonic."""
        with self.lock:
            state = self.rule.state(now)
        if wall is not None:
            for key in ("last_seen_at", "last_check_at"):
                if state[key] is not None:
                    state[key] = wall - (now - state[key])
        return state

    def check_once(self, open_capture, detector, at):
        """One check: grab a frame, classify it, release it. The frame is never kept."""
        result = "failed"
        capture = frame = None
        try:
            capture = open_capture(self.index)
            ok, frame = capture.read()
            if ok and frame is not None:
                result = "seen" if detector.detect(frame) else "not_seen"
        except Exception as error:  # any capture or detector failure is one failed check
            self.report(error)
        finally:
            frame = None
            if capture is not None:
                capture.release()
        self.record(result, at)

    def report(self, error):
        """Print the reason on stderr once per kind of failure (stdout carries the status lines)."""
        reason = f"{type(error).__name__}: {error}"
        if reason != self.last_error:
            self.last_error = reason
            print(f"Camera check failed: {reason}", file=sys.stderr, flush=True)

    def run(self):
        import cv2
        from person_detector import PersonDetector

        detector, failure = self.detector, None
        if detector is None:
            try:
                detector = PersonDetector(self.confidence)
            except Exception as error:
                failure = error
        while not self.stop.is_set():
            started = time.monotonic()
            if failure is not None:
                self.report(failure)
                self.record("failed", started)
            else:
                self.check_once(cv2.VideoCapture, detector, started)
            self.stop.wait(max(0, self.interval_s - (time.monotonic() - started)))
