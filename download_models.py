"""Downloads the two ready-made AI models into a 'models' folder. Run once:  python download_models.py"""

import os
import urllib.request

FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(FOLDER, exist_ok=True)

FILES = {
    # YOLO face detector (small and fast). Community model trained to find faces.
    "yolov8n-face.pt": [
        "https://github.com/lindevs/yolov8-face/releases/latest/download/yolov8n-face-lindevs.pt",
    ],
    # SFace face recognition model from the OpenCV Model Zoo.
    "face_recognition_sface_2021dec.onnx": [
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/"
        "face_recognition_sface_2021dec.onnx",
    ],
}

ok = True
for name, urls in FILES.items():
    path = os.path.join(FOLDER, name)
    if os.path.isfile(path) and os.path.getsize(path) > 100_000:
        print("already have", name)
        continue
    for url in urls:
        try:
            print("downloading", name, "...")
            urllib.request.urlretrieve(url, path)
            if os.path.getsize(path) > 100_000:
                print("  done:", round(os.path.getsize(path) / 1e6, 1), "MB")
                break
            os.remove(path)
        except Exception as e:
            print("  failed:", e)
    else:
        ok = False
        print(f"\nCould not download {name}. Download it by hand from your browser:")
        print(
            "  YOLO face : https://github.com/lindevs/yolov8-face/releases  (get yolov8n-face-lindevs.pt,"
        )
        print("              then rename it to yolov8n-face.pt)")
        print(
            "  SFace     : https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface"
        )
        print(f"and save it inside this folder: {FOLDER}\n")

print(
    "All models ready. Now run:  python smartgate_yolo.py"
    if ok
    else "Some files are missing (see above)."
)
