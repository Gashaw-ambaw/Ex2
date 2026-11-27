"""Counts the people in a photo with YOLOX on the whole picture and on overlapping tiles (D37).
Nothing is identified or saved: the input is a picture in memory and the result is a number."""
import threading
from pathlib import Path

import cv2

from app.yolox_zoo import YoloX, letterbox

MODEL = Path(__file__).parent / "models" / "object_detection_yolox_2022nov.onnx"
# Values chosen in spike S4 (spikes/s4/tile_count.py). Change them only together with a new measurement.
COLS, ROWS, OVERLAP = 3, 2, 0.2
SCORE, NMS_IOU = 0.2, 0.4
EDGE = 3  # pixels: a box this close to an inner tile edge is a cut person
PERSON = 0  # class number in the model


def tiles(width, height):
    """(x, y, w, h) of the whole photo and of the tiles."""
    w = width / (COLS - (COLS - 1) * OVERLAP)
    h = height / (ROWS - (ROWS - 1) * OVERLAP)
    grid = [(round(c * w * (1 - OVERLAP)), round(r * h * (1 - OVERLAP)), round(w), round(h))
            for r in range(ROWS) for c in range(COLS)]
    return [(0, 0, width, height)] + grid


class PeopleCounter:
    def __init__(self):
        self._model = None
        # The network is not safe for two requests at the same time.
        self._lock = threading.Lock()

    def count(self, image):
        """image: a BGR picture (numpy array). Returns the number of people."""
        height, width = image.shape[:2]
        boxes, scores = [], []
        with self._lock:
            if self._model is None:  # loaded on the first count, so the app starts fast
                self._model = YoloX(str(MODEL), confThreshold=SCORE, nmsThreshold=0.5, objThreshold=0.5)
            for x, y, w, h in tiles(width, height):
                crop = image[y:y + h, x:x + w]
                h, w = crop.shape[:2]
                blob, ratio = letterbox(crop)
                for det in self._model.infer(blob):
                    if int(det[-1]) != PERSON:
                        continue
                    bx, by, bw, bh = (float(v) / ratio for v in det[:4])
                    cut = ((x > 0 and bx <= EDGE) or (y > 0 and by <= EDGE)
                           or (x + w < width and bx + bw >= w - EDGE) or (y + h < height and by + bh >= h - EDGE))
                    if not cut:
                        boxes.append([x + bx, y + by, bw, bh])
                        scores.append(float(det[-2]))
        # One merge over all tiles, so a person seen twice is counted once.
        return len(cv2.dnn.NMSBoxes(boxes, scores, SCORE, NMS_IOU)) if boxes else 0
