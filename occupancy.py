"""Local OpenCV occupancy checks with no frame retention."""
from threading import Event, Thread
import time


class CameraOccupancy:
    def __init__(self, index, interval_s=None):
        if interval_s is None:
            from settings import RUNTIME_DEFAULTS
            interval_s = RUNTIME_DEFAULTS["camera_interval_s"]
        self.index = index
        self.interval_s = interval_s
        self.observation = ("unknown", None)
        self.stop = Event()
        self.worker = Thread(target=self.run, daemon=True)

    def __enter__(self):
        self.worker.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.worker.join(timeout=1)

    def current(self, now):
        state, observed_at = self.observation
        if observed_at is None or now - observed_at > self.interval_s + 5:
            return "unknown"
        return state

    def observation_age(self, now):
        observed_at = self.observation[1]
        return None if observed_at is None else now - observed_at

    def run(self):
        import cv2

        detector = cv2.HOGDescriptor()
        detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        while not self.stop.is_set():
            started = time.monotonic()
            state = "unknown"
            capture = None
            try:
                capture = cv2.VideoCapture(self.index)
                ok, frame = capture.read()
                if ok and frame is not None and frame.shape[0] >= 128 and frame.shape[1] >= 64:
                    boxes, _ = detector.detectMultiScale(frame, winStride=(8, 8), scale=1.05)
                    if len(boxes):
                        state = "occupied"
            except cv2.error:
                pass
            finally:
                if capture is not None:
                    capture.release()
            self.observation = (state, started)
            self.stop.wait(max(0, self.interval_s - (time.monotonic() - started)))
