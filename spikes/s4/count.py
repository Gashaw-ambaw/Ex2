# S4 spike: counts people in photos with YOLOX (OpenCV Zoo code and model); prints count, time and peak memory.
# Run: python count.py <photo> [...]   Needs demo.py, the .onnx model and the current upstream yolox.py here.
import ctypes
import json
import statistics
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).parent
MODEL = HERE / "object_detection_yolox_2022nov.onnx"
SCORE = 0.03  # chosen on the tuning photos only (the demo uses 0.5)
RUNS = 3


def peak_memory_mb():
    """Peak working set of this process (Windows)."""
    names = ["PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
             "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage"]

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [(n, ctypes.c_size_t) for n in names]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    get = ctypes.windll.psapi.GetProcessMemoryInfo
    get.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
    assert get(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
    return counters.PeakWorkingSetSize / 2**20


def one_run(photo):
    """One count in a fresh process. BGR input, as in the official YOLOX preprocessing; NMS threshold 0.5."""
    start = time.perf_counter()
    import cv2
    from demo import letterbox
    from yolox import YoloX

    model = YoloX(str(MODEL), confThreshold=SCORE, nmsThreshold=0.5, objThreshold=0.5)
    loaded = time.perf_counter()
    image = cv2.imread(photo)
    assert image is not None, "cannot read the photo"
    blob, _ = letterbox(image)
    found = model.infer(blob)
    done = time.perf_counter()
    count = sum(1 for det in found if int(det[-1]) == 0)  # class 0 = person
    print(json.dumps({"count": count, "load": loaded - start, "seconds": done - loaded,
                      "memory": peak_memory_mb(), "size": [image.shape[1], image.shape[0]]}))


def main(photos):
    for photo in photos:
        runs = []
        for _ in range(RUNS):
            output = subprocess.run([sys.executable, __file__, "--one", photo],
                                    capture_output=True, text=True, check=True).stdout
            runs.append(json.loads(output.strip().splitlines()[-1]))
        width, height = runs[0]["size"]
        print(f"{Path(photo).name}: {width}x{height}, counts {[r['count'] for r in runs]}, "
              f"median count time {statistics.median(r['seconds'] for r in runs):.2f} s, "
              f"median load {statistics.median(r['load'] for r in runs):.2f} s, "
              f"peak memory {max(r['memory'] for r in runs):.0f} MB")


if __name__ == "__main__":
    if sys.argv[1] == "--one":
        one_run(sys.argv[2])
    else:
        main(sys.argv[1:])
