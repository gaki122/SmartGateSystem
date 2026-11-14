# Smart Gate

Smart Gate is a desktop entry and exit management application for Samtse College of Education. It uses a webcam and face recognition to verify registered people and record access events.

## Features

- Register students, lecturers, and guests.
- Detect faces in a live camera feed with a pretrained YOLO face model.
- Compare detected faces with enrolled people using OpenCV SFace.
- Record entry and exit events and review access records.
- Manage staff accounts with role-based access.
- Export access records to CSV.
- Store application data in a local SQLite database.

Recognition depends on camera quality, lighting, and the enrolled face images. Always have a responsible person review access decisions; this project is a demonstration system, not a substitute for institutional security procedures.

## How it works

1. YOLO detects faces in webcam frames.
2. SFace creates a face representation and compares it with registered face data.
3. After a successful verification, the app records an entry or exit event in SQLite.

The models are pretrained; this project does not train them.

## Requirements

- Windows, macOS, or Linux with Python 3.10 or newer.
- A webcam for live registration and verification.
- Internet access for the initial model download.
- Python packages: `ultralytics`, `opencv-python`, `pillow`, and `numpy`.

The app also requires OpenCV's `FaceRecognizerSF` API. If it is unavailable in your OpenCV installation, install `opencv-contrib-python` instead of `opencv-python`. Do not install multiple OpenCV wheel variants in the same environment.

## Setup

Open a terminal in the project folder:

```powershell
cd C:\path\to\SmartGateSystem
```

Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell prevents activation, open Command Prompt and run:

```bat
.venv\Scripts\activate.bat
```

Install the packages:

```powershell
python -m pip install --upgrade pip
python -m pip install ultralytics opencv-python pillow numpy
```

If the app reports that `FaceRecognizerSF` is unavailable, replace the OpenCV package in the active environment:

```powershell
python -m pip uninstall -y opencv-python
python -m pip install opencv-contrib-python
```

Download the required face models:

```powershell
python download_models.py
```

The script saves `yolov8n-face.pt` and `face_recognition_sface_2021dec.onnx` in the `models` folder.

## Run

Start the application from the project folder:

```powershell
python smartgate_yolo.py
```

On the first launch, create the initial System Administrator account. Sign in, register test users, then use **Face Verification** to demonstrate the camera flow and access-record logging. Use a real webcam and good, even lighting for the demonstration.

To recover a full-access staff account's password:

```powershell
python smartgate_yolo.py --reset-admin
```

To erase all staff accounts, registered people, face images, and access logs and start over:

```powershell
python smartgate_yolo.py --reset-data
```

**Warning:** `--reset-data` permanently deletes application data. Use it only when you intend to reset the demo.

## Project files

| File or folder | Purpose |
| --- | --- |
| `smartgate_yolo.py` | Main Tkinter application, database, and face-recognition flow |
| `dashboard.py` | Dashboard interface |
| `registration.py` | Person registration interface |
| `user_management.py` | Staff-account management interface |
| `welcome_screen.py` | Welcome screen |
| `download_models.py` | Downloads the required pretrained model files |
| `models/` | Model files used by the app |
| `smartgate_yolo.db` | Local SQLite app data; created or updated by the app |
| `faces_yolo/` | Local registered face images |

## Privacy and GitHub

The database and face images may contain personal or biometric data. Do not publish real user records, credentials, face images, or database files to GitHub. Use synthetic demo data, and check the repository contents before making it public. Keep downloaded model files in line with their respective licenses and terms.

## Technologies and references

- [Ultralytics documentation](https://docs.ultralytics.com/)
- [OpenCV FaceRecognizerSF API](https://docs.opencv.org/4.x/da/d09/classcv_1_1FaceRecognizerSF.html)
- [OpenCV Zoo SFace model](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface)
- [YOLOv8 face model release](https://github.com/lindevs/yolov8-face/releases)
- Python standard library: Tkinter, SQLite, CSV, and threading

Check the licenses and attribution requirements of each third-party model and package before redistribution.

## Team

| Student Name | Student Number |
| --- | --- |
| Chimi Wangmo | 08230107 |
| Dema Lhamo | 08230116 |
| Lekzin Cheki Wangmo | 08230154 |
| Rinzin Wangmo | 08230181 |
| Tshering Choden | 08230220 |
