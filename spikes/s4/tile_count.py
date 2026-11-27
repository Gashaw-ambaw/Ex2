# S4 spike: counts people with YOLOX on the full photo plus overlapping tiles (own tiler, OpenCV only).
# Run: python tile_count.py tune          (5 tuning photos)   |   python tile_count.py cols rows overlap score iou <photo> ...
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

from count import MODEL, RUNS, peak_memory_mb  # count.py itself stays unchanged (the fallback)

PHOTOS = Path(__file__).parent / "../../private_data/photos"
TUNING = {"p1": 38, "p15": 29, "p32": 42, "p3": 24, "p23": 37}  # manual counts by the user
LOWEST_SCORE = 0.03
EDGE = 3  # pixels: a box this close to an inner tile edge is a cut person


def tiles(width, height, cols, rows, overlap):
    """(x, y, w, h) of the whole photo and of cols x rows tiles that overlap by the given share."""
    w = width / (cols - (cols - 1) * overlap)
    h = height / (rows - (rows - 1) * overlap)
    grid = [(round(c * w * (1 - overlap)), round(r * h * (1 - overlap)), round(w), round(h))
            for r in range(rows) for c in range(cols)]
    return [(0, 0, width, height)] + grid


def detections(model, image, cols, rows, overlap):
    """Person boxes (x, y, w, h in photo pixels) and scores, before the global NMS."""
    from demo import letterbox

    height, width = image.shape[:2]
    boxes, scores = [], []
    for x, y, w, h in tiles(width, height, cols, rows, overlap):
        crop = image[y:y + h, x:x + w]
        h, w = crop.shape[:2]
        blob, ratio = letterbox(crop)
        for det in model.infer(blob):
            if int(det[-1]) != 0:  # class 0 = person
                continue
            bx, by, bw, bh = (float(v) / ratio for v in det[:4])
            cut = ((x > 0 and bx <= EDGE) or (y > 0 and by <= EDGE)
                   or (x + w < width and bx + bw >= w - EDGE) or (y + h < height and by + bh >= h - EDGE))
            if not cut:
                boxes.append([x + bx, y + by, bw, bh])
                scores.append(float(det[-2]))
    return boxes, scores


def merged_count(boxes, scores, score, iou):
    """One NMS over all tiles, so a person seen in two tiles is counted once."""
    import cv2

    return len(cv2.dnn.NMSBoxes(boxes, scores, score, iou)) if boxes else 0


def load_model(score):
    from yolox import YoloX

    return YoloX(str(MODEL), confThreshold=score, nmsThreshold=0.5, objThreshold=0.5)


def tune():
    import cv2

    model = load_model(LOWEST_SCORE)
    results = []
    for cols, rows in ((2, 2), (3, 2), (3, 3)):
        for overlap in (0.2, 0.3):
            found = [detections(model, cv2.imread(str(PHOTOS / f"{name}.jpeg")), cols, rows, overlap)
                     for name in TUNING]
            for score in (0.03, 0.1, 0.2, 0.3):
                for iou in (0.4, 0.5):
                    got = [merged_count(b, s, score, iou) for b, s in found]
                    errors = [(g - m) / m * 100 for g, m in zip(got, TUNING.values())]
                    results.append((statistics.mean(map(abs, errors)), -sum(abs(e) <= 10 for e in errors),
                                    cols, rows, overlap, score, iou, got))
    results.sort(key=lambda r: r[:2])
    print(f"{len(results)} settings; manual {list(TUNING.values())}. Best 8 (tuning photos only):")
    for error, within, cols, rows, overlap, score, iou, got in results[:8]:
        print(f"{cols}x{rows} overlap {overlap} score {score} iou {iou}: {got} "
              f"mean abs err {error:.1f}%, within 10%: {-within}")


def one_run(cols, rows, overlap, score, iou, photo):
    start = time.perf_counter()
    import cv2

    model = load_model(score)
    loaded = time.perf_counter()
    image = cv2.imread(photo)
    assert image is not None, "cannot read the photo"
    count = merged_count(*detections(model, image, cols, rows, overlap), score, iou)
    done = time.perf_counter()
    print(json.dumps({"count": count, "load": loaded - start, "seconds": done - loaded, "memory": peak_memory_mb()}))


def measure(settings, photos):
    for photo in photos:
        runs = []
        for _ in range(RUNS):
            command = [sys.executable, __file__, "--one", *settings, photo]
            output = subprocess.run(command, capture_output=True, text=True, check=True).stdout
            runs.append(json.loads(output.strip().splitlines()[-1]))
        print(f"{Path(photo).name}: counts {[r['count'] for r in runs]}, "
              f"median count time {statistics.median(r['seconds'] for r in runs):.2f} s, "
              f"median load {statistics.median(r['load'] for r in runs):.2f} s, "
              f"peak memory {max(r['memory'] for r in runs):.0f} MB")


def parse(args):
    return int(args[0]), int(args[1]), float(args[2]), float(args[3]), float(args[4])


if __name__ == "__main__":
    if sys.argv[1] == "tune":
        tune()
    elif sys.argv[1] == "--one":
        one_run(*parse(sys.argv[2:7]), sys.argv[7])
    else:
        measure(sys.argv[1:6], sys.argv[6:])
