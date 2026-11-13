"""
Smart Gate - Samtse College of Education  (YOLO face detection + SFace recognition edition)

Both AI models are ready-made (pretrained). We do not train anything ourselves.
    YOLO (yolov8n-face)  -> finds the face in the camera picture
    SFace (OpenCV)       -> turns a face into numbers ("face fingerprint") so people can be told apart

Setup:
    pip install ultralytics opencv-python pillow numpy
    python download_models.py
Run:
    python smartgate_yolo.py

Page modules:
    dashboard.py       Dashboard interface
    registration.py    Student, lecturer, and guest registration
    user_management.py Staff account management
"""

# Code
import csv
import hashlib
import hmac
import importlib.util
import os
import secrets
import re
import shutil
import smtplib
import sqlite3
import ssl
import statistics
import sys
import threading
import time
import tkinter as tk
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from tkinter import filedialog, messagebox, ttk

if __name__ == "__main__":
    sys.modules.setdefault("smartgate_yolo", sys.modules[__name__])

MODEL_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "models"
)  # (__file__) is this program's own file . abspath -gives its full address
YOLO_WEIGHTS = os.path.join(MODEL_DIR, "yolov8n-face.pt")
SFACE_MODEL = os.path.join(MODEL_DIR, "face_recognition_sface_2021dec.onnx")
YUNET_MODEL = os.path.join(
    MODEL_DIR, "face_detection_yunet_2023mar.onnx"
)  # OPTIONAL: lets us align faces

PROBLEM = None
try:
    import cv2
    import numpy as np
    from PIL import Image, ImageTk

    if (
        importlib.util.find_spec("ultralytics") is None
    ):  # checked only; the slow import happens later
        raise ImportError("No module named 'ultralytics'")
    if not hasattr(cv2, "FaceRecognizerSF"):
        PROBLEM = "Your OpenCV is too old. Run:  pip install -U opencv-python"
    elif not (os.path.isfile(YOLO_WEIGHTS) and os.path.isfile(SFACE_MODEL)):
        PROBLEM = "The model files are missing. Run:  python download_models.py"
except ImportError as e:
    PROBLEM = (
        "A package is missing (" + str(e) + ").\nRun:\n"
        "    pip install ultralytics opencv-python pillow numpy"
    )
DEPS_OK = PROBLEM is None

# ======================================================================
# SECTION 1: IMPORTED DEPENDENCIES, MODEL PATHS, THEME, AND SETTINGS
# ======================================================================
# Theme
NAVY, NAVY_ACTIVE = "#0F2A47", "#1E4266"
PRIMARY, PRIMARY_D = "#00629B", "#004E7C"
GREEN, GREEN_L, RED = "#10B981", "#D1FAE5", "#EF4444"
BG, CARD, BORDER = "#F8FAFC", "#FFFFFF", "#E2E8F0"
INK, MUTED, FIELD = "#0F2A47", "#64748B", "#F1F5F9"
FONT = "Georgia"


def F(size=10, w="normal"):
    """Return a slightly enlarged UI font without overwhelming compact layouts."""
    return (FONT, max(8, int(size) + 1), w)

BST = timezone(timedelta(hours=6))  # Bhutan Standard Time
now = lambda: datetime.now(BST)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "smartgate_yolo.db")
FACE_DIR = os.path.join(BASE_DIR, "faces_yolo")  # faces_yolo/<ID>/<n>.png
# System Administrator and College Management have full access; Security Guards
# can verify faces and view access records.
FULL_ACCESS_ROLES = ("System Administrator", "College Management")
ROLES = [*FULL_ACCESS_ROLES, "Security Guards"]
PW_ROUNDS = 200_000  # password hashing strength (PBKDF2-SHA256)

# Password recovery by Gmail. Use a Gmail APP PASSWORD (not your normal Gmail password).
# Create it at: myaccount.google.com/apppasswords (2-Step Verification must be ON).
SENDER_EMAIL = ""  # e.g. "smartgate.sce@gmail.com"
SENDER_APP_PASSWORD = ""  # the 16-letter app password
SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 465
RESET_CODE_MINUTES = 10  # how long a recovery code works
RESET_MAX_TRIES = 5  # wrong-code attempts allowed

# Face recognition tuning
SHOTS = 1  # one face photo per person at registration
BURST = 15  # frames saved during that photo (~2 s) for better accuracy
# (no limit on retakes: the admin may retake the registration photo as many times as needed)
SAMPLES_NEEDED = SHOTS * BURST  # face images stored per person
STRICTNESS = "high"  # how exactly a face must match a registered person:
#   "normal"    = fewer rejections, a look-alike can sometimes pass
#   "high"      = recommended: look-alikes are rejected
#   "very_high" = strictest: real users may need good light and a straight face
_PRESETS = {"normal": (0.50, 0.08), "high": (0.60, 0.12), "very_high": (0.68, 0.15)}
MATCH_SIM, MATCH_MARGIN = _PRESETS[STRICTNESS]
# MATCH_SIM    = similarity (0 to 1) the best person must reach
# MATCH_MARGIN = the best person must beat the SECOND-best person by this much,
#                so a face that fits two people about equally is Unknown
CONFIRM_AVG_BONUS = (
    0.03  # the AVERAGE score over the confirmation frames must reach MATCH_SIM + this
)
SCORE_TOPK = (
    3  # a person's score = average of their best N saved faces (less lucky-frame noise)
)
DEBUG_SCORES = (
    True  # True = show the similarity number on the camera box so you can tune
)
# MATCH_SIM. Set to False before the final demo.
DUPLICATE_SIM = (
    0.363  # registration only: a new face this similar to a saved one is a duplicate.
)
# LOWER = blocks more duplicates; raise it if new people are wrongly blocked.
DUPLICATE_SHARE = 0.5  # share of the captured frames that must point to the same person
YOLO_CONF = 0.5  # YOLO must be at least this sure that something is a face
YOLO_SIZE = 480  # picture size given to YOLO (smaller = faster)
CONFIRM_FRAMES = 6  # same person must be matched this many frames in a row
MIN_FACE = 80  # smallest face (pixels) the camera will consider
VIEW_SIZE = (520, 390)  # size of the live preview on the verification page
SHOT_PROMPTS = ["Fill in the form first, then press Take Photo"]
PROGRAMMES_BY_TYPE = {
    "Student": ["MEd", "BEd", "PGDE", "PGDCCP", "MACC"],
    "Lecturer": ["Lecturer"],
    "Guest": ["Guest"],
}
CAMERA_INDEX = (
    1  # None = try cameras automatically. If the wrong camera opens (for example a
)
# virtual camera), run camera_test.py, find your webcam's number and set it here, e.g. CAMERA_INDEX = 1
CAMERA_INDEXES = 6  # when CAMERA_INDEX is None, camera numbers 0..5 are tried


# Account rules
def username_problem(v):
    if not v:
        return "Username is required."
    if not (v[0].isascii() and v[0].isalpha()):
        return "Username must start with a letter."
    bad = [c for c in v if not (c.isascii() and c.isalnum()) and c not in "._"]
    if bad:
        return f'Letters, numbers, "." and "_" only - "{bad[0]}" is not allowed.'
    if len(v) < 3:
        return "Username needs at least 3 characters."
    if len(v) > 20:
        return "Username is too long (maximum 20 characters)."
    return ""


def password_problem(v):
    if not v:
        return "Password is required."
    if " " in v:
        return "Password cannot contain spaces."
    if len(v) < 8:
        return f"Password needs at least 8 characters ({len(v)} so far)."
    if not any(c.isalpha() for c in v):
        return "Add at least one letter."
    if not any(c.isdigit() for c in v):
        return "Add at least one number."
    if len(v) > 50:
        return "Password is too long (maximum 50 characters)."
    return ""


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PW_ROUNDS
    ).hex()
    return salt, h


def send_reset_email(to_addr, code):
    """Email a password-recovery code through Gmail."""
    m = EmailMessage()
    m["Subject"] = "Smart Gate password reset code"
    m["From"] = SENDER_EMAIL
    m["To"] = to_addr
    m.set_content(
        f"Your Smart Gate recovery code is {code}\n\n"
        f"It expires in {RESET_CODE_MINUTES} minutes. "
        "If you did not ask for it, ignore this email."
    )
    with smtplib.SMTP_SSL(
        SMTP_HOST, SMTP_PORT, context=ssl.create_default_context(), timeout=15
    ) as s:
        s.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        s.send_message(m)


# ======================================================================
# SECTION 2: DATABASE LAYER (SQLite)
# ======================================================================
class DB:
    def __init__(self):
        self.c = sqlite3.connect(DB_PATH)
        self.c.row_factory = sqlite3.Row
        self.c.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                uid TEXT PRIMARY KEY, name TEXT, programme TEXT,
                type TEXT, faces INTEGER, course TEXT DEFAULT '', email TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT, action TEXT, ts TEXT);
            CREATE TABLE IF NOT EXISTS staff(
                username TEXT PRIMARY KEY, full_name TEXT, role TEXT,
                salt TEXT, pw TEXT, active INTEGER DEFAULT 1, created TEXT, last_login TEXT);
            CREATE TABLE IF NOT EXISTS app_meta(
                key TEXT PRIMARY KEY, value TEXT);""")
        # Migrate legacy roles once, preserving existing accounts and face/access data.
        migrated = self.c.execute(
            "SELECT value FROM app_meta WHERE key='role_schema_v3'"
        ).fetchone()
        if not migrated:
            # Keep existing System Administrator accounts as they are. Convert legacy
            # role labels without deleting or recreating any staff, users, or access logs.
            self.c.execute(
                "UPDATE staff SET role='College Management' WHERE role='Admin'"
            )
            self.c.execute(
                "UPDATE staff SET role='Security Guards' WHERE role IN ('Guard', 'Security Guard')"
            )
            self.c.execute(
                "INSERT INTO app_meta(key, value) VALUES('role_schema_v3', 'done')"
            )
        unified = self.c.execute(
            "SELECT value FROM app_meta WHERE key='role_schema_v4'"
        ).fetchone()
        if not unified:
            self.c.execute(
                "UPDATE staff SET role='System Administrator' "
                "WHERE role IN ('College Management', 'Admin')"
            )
            self.c.execute(
                "INSERT INTO app_meta(key, value) VALUES('role_schema_v4', 'done')"
            )
        # older database files: add the new columns
        have = [r[1] for r in self.c.execute("PRAGMA table_info(users)")]
        for col in ("course", "email"):
            if col not in have:
                self.c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT ''")
        self.c.commit()
        # staff table: add the recovery email column if it is missing (keeps all old data)
        staff_cols = [r[1] for r in self.c.execute("PRAGMA table_info(staff)")]
        if "email" not in staff_cols:
            self.c.execute("ALTER TABLE staff ADD COLUMN email TEXT DEFAULT ''")
        self.c.commit()

    # staff accounts (who may log in). Passwords are never stored, only a salted hash.
    def staff_count(self):
        return self.c.execute("SELECT COUNT(*) FROM staff").fetchone()[0]

    def staff_list(self):
        return self.c.execute("SELECT * FROM staff ORDER BY role, full_name").fetchall()

    def staff_get(self, username):
        return self.c.execute(
            "SELECT * FROM staff WHERE username=? COLLATE NOCASE", (username,)
        ).fetchone()

    def staff_by_email(self, email):
        return self.c.execute(
            "SELECT * FROM staff WHERE email<>'' AND email=? COLLATE NOCASE", (email,)
        ).fetchone()

    def add_staff(self, username, full_name, role, password, email=""):
        salt, h = hash_password(password)
        self.c.execute(
            "INSERT INTO staff(username,full_name,role,salt,pw,active,created,email) "
            "VALUES(?,?,?,?,?,1,?,?)",
            (
                username.lower(),
                full_name,
                role,
                salt,
                h,
                now().strftime("%Y-%m-%d %H:%M:%S"),
                email.lower(),
            ),
        )
        self.c.commit()

    def set_email(self, username, email):
        self.c.execute(
            "UPDATE staff SET email=? WHERE username=?", (email.lower(), username)
        )
        self.c.commit()

    def check_password(self, username, password):
        """The staff row if the password is right, else None."""
        r = self.staff_get(username)
        if not r:
            hash_password(password)  # same time spent, so usernames can't be guessed
            return None
        _, h = hash_password(password, r["salt"])
        return r if hmac.compare_digest(h, r["pw"]) else None

    def set_password(self, username, password):
        salt, h = hash_password(password)
        self.c.execute(
            "UPDATE staff SET salt=?, pw=? WHERE username=?", (salt, h, username)
        )
        self.c.commit()

    def set_username(self, old_username, new_username):
        """Change a staff login name without touching any other system data."""
        self.c.execute(
            "UPDATE staff SET username=? WHERE username=?",
            (new_username.lower(), old_username),
        )
        self.c.commit()

    def set_role(self, username, role):
        self.c.execute("UPDATE staff SET role=? WHERE username=?", (role, username))
        self.c.commit()

    def set_active(self, username, active):
        self.c.execute(
            "UPDATE staff SET active=? WHERE username=?", (1 if active else 0, username)
        )
        self.c.commit()

    def delete_staff(self, username):
        self.c.execute("DELETE FROM staff WHERE username=?", (username,))
        self.c.commit()

    def touch_login(self, username):
        self.c.execute(
            "UPDATE staff SET last_login=? WHERE username=?",
            (now().strftime("%Y-%m-%d %H:%M:%S"), username),
        )
        self.c.commit()

    def active_admins(self):
        # Keep at least one active full-access account to manage staff accounts.
        return self.c.execute(
            "SELECT COUNT(*) FROM staff WHERE role IN (?, ?) AND active=1",
            FULL_ACCESS_ROLES,
        ).fetchone()[0]

    # users
    def users(self):
        return self.c.execute("SELECT * FROM users ORDER BY name").fetchall()

    def user(self, uid):
        return self.c.execute("SELECT * FROM users WHERE uid=?", (uid,)).fetchone()

    def uid_taken(self, uid):
        return (
            self.c.execute(
                "SELECT 1 FROM users WHERE uid=? COLLATE NOCASE", (uid,)
            ).fetchone()
            is not None
        )

    def email_taken(self, email):
        return (
            self.c.execute(
                "SELECT 1 FROM users WHERE email=? COLLATE NOCASE", (email,)
            ).fetchone()
            is not None
        )

    def add_user(self, uid, name, prog, utype, faces, course="", email=""):
        self.c.execute(
            "INSERT INTO users(uid,name,programme,type,faces,course,email) "
            "VALUES(?,?,?,?,?,?,?)",
            (uid, name, prog, utype, faces, course, email),
        )
        self.c.commit()

    # logs
    def record_gate_event(self, uid):
        self.c.execute("BEGIN IMMEDIATE")
        try:
            row = self.c.execute(
                "SELECT action FROM logs WHERE uid=? ORDER BY id DESC LIMIT 1", (uid,)
            ).fetchone()
            action = "Exit" if row and row["action"] == "Entry" else "Entry"
            timestamp = now().strftime("%Y-%m-%d %H:%M:%S")
            self.c.execute(
                "INSERT INTO logs(uid,action,ts) VALUES(?,?,?)",
                (uid, action, timestamp),
            )
            self.c.commit()
        except sqlite3.Error:
            self.c.rollback()
            raise
        return action, timestamp

    def status(self, uid):
        r = self.c.execute(
            "SELECT action FROM logs WHERE uid=? ORDER BY id DESC LIMIT 1", (uid,)
        ).fetchone()
        return "Inside" if r and r["action"] == "Entry" else "Outside"

    def latest_rows(self):
        """One row per user that has any log: their most recent event."""
        return self.c.execute("""
            SELECT u.uid, u.name, u.type, l.action, l.ts FROM users u
            JOIN logs l ON l.id=(SELECT MAX(id) FROM logs WHERE uid=u.uid)
            ORDER BY l.id DESC""").fetchall()

    def today_logs(self):
        d = now().strftime("%Y-%m-%d")
        return self.c.execute(
            "SELECT * FROM logs WHERE ts LIKE ?", (d + "%",)
        ).fetchall()

    def counts(self):
        us = self.users()
        inside = [u for u in us if self.status(u["uid"]) == "Inside"]
        by = lambda lst, t: sum(1 for u in lst if u["type"] == t)
        return dict(
            total=len(us),
            inside=len(inside),
            students=by(inside, "Student"),
            lecturers=by(inside, "Lecturer"),
            reg_students=by(us, "Student"),
            reg_lecturers=by(us, "Lecturer"),
            reg_guests=by(us, "Guest"),
            in_guests=by(inside, "Guest"),
        )

    def user_logs(self, uid):
        return self.c.execute(
            "SELECT * FROM logs WHERE uid=? ORDER BY id DESC", (uid,)
        ).fetchall()

    def delete_user(self, uid):
        self.c.execute("DELETE FROM logs WHERE uid=?", (uid,))
        self.c.execute("DELETE FROM users WHERE uid=?", (uid,))
        self.c.commit()

    def recent_logs(self, n=5):
        return self.c.execute(
            """SELECT l.*, u.name, u.type FROM logs l
                                 JOIN users u ON u.uid=l.uid
                                 ORDER BY l.id DESC LIMIT ?""",
            (n,),
        ).fetchall()

    def logs_full(self, action=None, today=True):
        sql = (
            "SELECT l.*, u.name, u.type, u.programme, u.course, u.email "
            "FROM logs l JOIN users u ON u.uid=l.uid WHERE 1=1"
        )
        args = []
        if today:
            sql += " AND l.ts LIKE ?"
            args.append(now().strftime("%Y-%m-%d") + "%")
        if action:
            sql += " AND l.action=?"
            args.append(action)
        return self.c.execute(sql + " ORDER BY l.id DESC", args).fetchall()


# ======================================================================
# SECTION 3: FACE RECOGNITION ENGINE (YOLO + SFace)
# ======================================================================
# Face engine
class FaceEngine:
    """YOLO finds faces; SFace turns each face into 128 numbers. A face is accepted only if it is
    similar enough to a registered person; otherwise it is Unknown (None) and never gets a name.
    """

    def __init__(self):
        from ultralytics import YOLO  # slow import: done here, in the background loader

        self.yolo = YOLO(YOLO_WEIGHTS)
        self.sface = cv2.FaceRecognizerSF.create(SFACE_MODEL, "")
        self.yunet, self._landmarks = None, []
        if os.path.isfile(
            YUNET_MODEL
        ):  # optional: finds eyes/nose/mouth to align faces
            try:
                self.yunet = cv2.FaceDetectorYN.create(
                    YUNET_MODEL, "", (320, 320), 0.6, 0.3, 5000
                )
            except Exception:
                self.yunet = None
        print(
            "Face alignment:",
            (
                "ON"
                if self.yunet is not None
                else "OFF (optional: add models/face_detection_yunet_2023mar.onnx for stricter matching)"
            ),
        )
        self.feats = np.zeros((0, 128), np.float32)  # one row per saved face image
        self.owner = []  # the person ID of each row
        self.groups = {}  # person ID -> row numbers in self.feats
        self.rec = None  # None = nobody registered yet
        self.train()

    def detect(self, frame):
        """-> (copy of the picture, [(x, y, w, h), ...]) for faces found by YOLO."""
        res = self.yolo.predict(frame, imgsz=YOLO_SIZE, conf=YOLO_CONF, verbose=False)[
            0
        ]
        boxes = []
        for x1, y1, x2, y2 in res.boxes.xyxy.cpu().numpy():
            w, h = x2 - x1, y2 - y1
            if min(w, h) >= MIN_FACE:
                boxes.append((int(x1), int(y1), int(w), int(h)))
        self._landmarks = []
        if self.yunet is not None and boxes:
            try:
                self.yunet.setInputSize((frame.shape[1], frame.shape[0]))
                _, found = self.yunet.detect(frame)
                if found is not None:
                    self._landmarks = list(found)
            except Exception:
                self._landmarks = []
        return frame.copy(), boxes

    def _landmark_row(self, box):
        """The YuNet face (with eye/nose/mouth points) that sits on this YOLO box, or None."""
        x, y, w, h = box
        best, best_iou = None, 0.25
        for row in self._landmarks:
            fx, fy, fw, fh = row[0], row[1], row[2], row[3]
            ix = max(0.0, min(x + w, fx + fw) - max(x, fx))
            iy = max(0.0, min(y + h, fy + fh) - max(y, fy))
            inter = ix * iy
            iou = inter / (w * h + fw * fh - inter + 1e-9)
            if iou > best_iou:
                best, best_iou = row, iou
        return best

    def crop(self, frame, box):
        """A 112x112 face picture for SFace. If the optional YuNet model is present the face is
        ALIGNED (eyes level and centred), which separates look-alikes much better; otherwise a
        square crop around the face is used."""
        row = self._landmark_row(box) if self.yunet is not None else None
        if row is not None:
            try:
                return self.sface.alignCrop(frame, row)
            except Exception:
                pass
        x, y, w, h = box
        side = int(max(w, h) * 1.15)
        cx, cy = x + w // 2, y + h // 2
        x0, y0 = max(cx - side // 2, 0), max(cy - side // 2, 0)
        x1, y1 = min(x0 + side, frame.shape[1]), min(y0 + side, frame.shape[0])
        return cv2.resize(frame[y0:y1, x0:x1], (112, 112))

    def embed(self, face):
        f = self.sface.feature(face).flatten().astype(np.float32)
        return f / (np.linalg.norm(f) + 1e-9)

    def train(self):
        """Rebuild the list of face fingerprints from the saved face images."""
        rows, self.owner = [], []
        if os.path.isdir(FACE_DIR):
            for uid in sorted(os.listdir(FACE_DIR)):
                folder = os.path.join(FACE_DIR, uid)
                if not os.path.isdir(folder):
                    continue
                for fn in sorted(os.listdir(folder)):
                    if fn.lower().endswith(".png"):
                        im = cv2.imread(os.path.join(folder, fn))
                        if im is not None:
                            rows.append(self.embed(cv2.resize(im, (112, 112))))
                            self.owner.append(uid)
        self.feats = (
            np.array(rows, np.float32) if rows else np.zeros((0, 128), np.float32)
        )
        self.rec = True if rows else None
        # row numbers of each person's saved faces, so every person gets ONE combined score
        self.groups = {}
        for i, uid in enumerate(self.owner):
            self.groups.setdefault(uid, []).append(i)
        self.groups = {uid: np.array(ix) for uid, ix in self.groups.items()}

    def nearest(self, face):
        """-> (person ID, similarity) of the most similar saved face, or (None, -1)."""
        if self.rec is None:
            return None, -1.0
        sims = self.feats @ self.embed(face)
        i = int(np.argmax(sims))
        return self.owner[i], float(sims[i])

    def scores(self, face):
        """-> {person ID: similarity}. Each person's score is the average of their best
        SCORE_TOPK saved faces, so one lucky frame cannot decide who someone is."""
        q = self.embed(face)
        sims = self.feats @ q
        return {
            uid: float(np.sort(sims[ix])[::-1][:SCORE_TOPK].mean())
            for uid, ix in self.groups.items()
        }

    def predict(self, face):
        """-> (person ID or None, distance). None means 'not a registered person'.
        A face is accepted only when BOTH rules pass:
          1. the best person scores at least MATCH_SIM, and
          2. the best person beats the second-best person by at least MATCH_MARGIN
             (this is what stops a look-alike from being taken for someone else)."""
        if self.rec is None:
            return None, 1.0
        ranked = sorted(self.scores(face).items(), key=lambda kv: kv[1], reverse=True)
        best_uid, best = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else -1.0
        if best >= MATCH_SIM and (best - second) >= MATCH_MARGIN:
            return best_uid, 1 - best
        return None, 1 - best

    def find_duplicate(self, faces):
        """Return the ID of an already-registered person these faces belong to, else None."""
        if self.rec is None or not faces:
            return None
        near = {}
        for f in faces:
            uid, sim = self.nearest(f)
            if uid is not None:
                near.setdefault(uid, []).append(sim)
        if not near:
            return None
        uid, sims = max(near.items(), key=lambda kv: len(kv[1]))
        if (
            len(sims) >= len(faces) * DUPLICATE_SHARE
            and statistics.median(sims) >= DUPLICATE_SIM
        ):
            return uid
        return None

    def save(self, uid, faces):
        folder = os.path.join(FACE_DIR, uid)
        os.makedirs(folder, exist_ok=True)
        for i, f in enumerate(faces):
            cv2.imwrite(os.path.join(folder, f"{i:03d}.png"), f)
        self.train()

    def remove(self, uid):
        shutil.rmtree(os.path.join(FACE_DIR, uid), ignore_errors=True)
        self.train()


# ======================================================================
# SECTION 4: CAMERA ACCESS
# ======================================================================
class Camera:
    """Reads the webcam on a background thread so the UI never blocks."""

    @staticmethod
    def _backends():
        if os.name == "nt":  # Windows: DirectShow, then Media Foundation
            return [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
        return [cv2.CAP_ANY]

    def __init__(self, index=None):
        self.cap, self.frame, self.thread = None, None, None
        self.lock = threading.Lock()
        self.running = False
        self.index = None
        indexes = [index] if index is not None else list(range(CAMERA_INDEXES))
        for idx in indexes:  # try each camera + backend until a real
            for backend in self._backends():  # picture comes back (not just "opened")
                cap = cv2.VideoCapture(idx, backend)
                if not cap.isOpened():
                    cap.release()
                    continue
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                got = None
                for _ in range(30):  # cameras need a moment to warm up
                    ok, f = cap.read()
                    if ok and f is not None and f.size:
                        got = f
                        break
                    time.sleep(0.1)
                if got is None:
                    cap.release()
                    continue
                self.cap, self.index, self.running = cap, idx, True
                self.frame = cv2.flip(got, 1)
                self.thread = threading.Thread(target=self._loop, daemon=True)
                self.thread.start()
                return
        self.cap = None

    def _loop(self):
        while self.running:
            ok, f = self.cap.read()
            if ok:
                with self.lock:
                    self.frame = cv2.flip(f, 1)  # mirror view, used everywhere
            else:
                time.sleep(0.05)

    def read(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.5)
        if self.cap is not None:
            self.cap.release()


# Widgets
# ======================================================================
# SECTION 5: REUSABLE UI WIDGETS (buttons, form fields, and shared controls)
# ======================================================================
class Btn(tk.Label):
    STYLES = {
        "primary": (PRIMARY, "white", PRIMARY_D, PRIMARY),
        "green": (GREEN, "white", "#0EA371", GREEN),
        "outline": (CARD, PRIMARY, "#EAF3FB", PRIMARY),
        "red": (RED, "white", "#DC2626", RED),
    }

    def __init__(self, parent, text, command, style="primary", **kw):
        bg, fg, self.hover, border = self.STYLES[style]
        self.base = bg
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=F(10, "bold"),
            cursor="hand2",
            pady=10,
            highlightthickness=1,
            highlightbackground=border,
            **kw,
        )
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Enter>", lambda e: self.config(bg=self.hover))
        self.bind("<Leave>", lambda e: self.config(bg=self.base))


def card(parent, **kw):
    return tk.Frame(
        parent,
        bg=CARD,
        highlightthickness=1,
        highlightbackground=kw.pop("border", BORDER),
        **kw,
    )


def clickable(widget, cmd, tint=False):
    """Make a widget (and all children) clickable with a hover effect."""

    def paint(w, color):
        if not isinstance(w, tk.Canvas):
            try:
                w.config(bg=color)
            except tk.TclError:
                pass
        for ch in w.winfo_children():
            paint(ch, color)

    def enter(e):
        if tint:
            paint(widget, "#EEF5FB")
        elif int(widget.cget("highlightthickness")) > 0:
            widget.config(highlightbackground=PRIMARY)

    def leave(e):
        x, y = widget.winfo_pointerxy()
        under = widget.winfo_containing(x, y)
        if under is not None and (
            str(under) == str(widget) or str(under).startswith(str(widget) + ".")
        ):
            return
        if tint:
            paint(widget, CARD)
        elif int(widget.cget("highlightthickness")) > 0:
            widget.config(highlightbackground=BORDER)

    def bind_all(w):
        w.bind("<Button-1>", lambda e: cmd())
        w.bind("<Enter>", enter, add="+")
        w.bind("<Leave>", leave, add="+")
        w.config(cursor="hand2")
        for ch in w.winfo_children():
            bind_all(ch)

    bind_all(widget)


class FormField(tk.Frame):
    """Labeled entry with inline validation error text and optional password toggle."""

    def __init__(self, parent, label, show=None, required=True, hint=None, wrap=0):
        super().__init__(parent, bg=parent["bg"])
        top = tk.Frame(self, bg=parent["bg"])
        top.pack(fill="x", pady=(8, 3))
        tk.Label(
            top,
            text=label.upper() + ("  *" if required else ""),
            bg=parent["bg"],
            fg=PRIMARY,
            font=F(8, "bold"),
        ).pack(side="left")
        if hint:
            tk.Label(top, text=hint, bg=parent["bg"], fg=MUTED, font=F(7)).pack(
                side="right"
            )
        row = tk.Frame(
            self,
            bg=FIELD,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=PRIMARY,
        )
        row.pack(fill="x")
        self._show = show
        self.entry = tk.Entry(
            row,
            bg=FIELD,
            fg=INK,
            relief="flat",
            font=F(10),
            show=show,
            insertbackground=INK,
            highlightthickness=0,
            bd=0,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(8, 4))
        self.row = row
        self.toggle = None
        if show:
            self.toggle = tk.Label(
                row,
                text="Show",
                bg=FIELD,
                fg=PRIMARY,
                font=F(7, "bold"),
                cursor="hand2",
            )
            self.toggle.pack(side="right", padx=8)
            self.toggle.bind("<Button-1>", lambda e: self._flip())
        self.err = tk.Label(
            self,
            text="",
            bg=parent["bg"],
            fg=RED,
            font=F(7),
            anchor="w",
            justify="left",
            wraplength=wrap,
        )
        self.err.pack(fill="x", pady=(2, 0))
        self._wrap = wrap
        self.bind("<Configure>", self._fit_error)
        self.entry.bind("<Key>", lambda e: self.ok())
        self.checker = None

    def _fit_error(self, event):
        available = max(120, event.width - 8)
        wrap = min(self._wrap, available) if self._wrap else available
        if self.err.cget("wraplength") != wrap:
            self.err.config(wraplength=wrap)

    def _flip(self):
        if self.entry.cget("show") == "":
            self.entry.config(show=self._show)
            self.toggle.config(text="Show")
        else:
            self.entry.config(show="")
            self.toggle.config(text="Hide")

    def get(self):
        return self.entry.get().strip()

    def error(self, msg):
        self.row.config(highlightbackground=RED, highlightcolor=RED)
        self.err.config(text="⚠ " + msg)

    def ok(self):
        self.row.config(highlightbackground=BORDER, highlightcolor=PRIMARY)
        self.err.config(text="")

    def good(self):
        self.row.config(highlightbackground=GREEN, highlightcolor=GREEN)
        self.err.config(text="")

    def live(self, checker, on_change=None):
        """Check the text while the person types. checker(text) returns an error text or ''."""
        self.checker = checker
        self.on_change = on_change
        self.entry.bind("<KeyRelease>", lambda e: self.check_now(), add="+")
        self.entry.bind("<FocusOut>", lambda e: self.check_now(True), add="+")

    def check_now(self, leaving=False):
        text = self.entry.get().strip()
        if not text:
            if leaving:
                msg = self.checker("")
                if msg:
                    self.error(msg)
                    return
            self.ok()
        else:
            msg = self.checker(text)
            if msg:
                self.error(msg)
            else:
                self.good()
        if getattr(self, "on_change", None):
            self.on_change()

    def focus(self):
        self.entry.focus()

    def bind_return(self, cmd):
        self.entry.bind("<Return>", lambda e: cmd())


class ComboField(tk.Frame):
    """Labeled drop-down list with an inline error line (same look as FormField)."""

    def __init__(self, parent, label, values, required=True):
        super().__init__(parent, bg=parent["bg"])
        tk.Label(
            self,
            text=label.upper() + ("  *" if required else ""),
            bg=parent["bg"],
            fg=PRIMARY,
            font=F(8, "bold"),
        ).pack(anchor="w", pady=(12, 4))
        self.box = ttk.Combobox(self, values=values, state="readonly", font=F(10))
        self.box.pack(fill="x", ipady=5)
        self.err = tk.Label(
            self,
            text="",
            bg=parent["bg"],
            fg=RED,
            font=F(7),
            anchor="w",
            justify="left",
            wraplength=230,
        )
        self.err.pack(fill="x", pady=(2, 0))
        self.box_width = 230
        self.bind("<Configure>", self._fit_error)
        self.box.bind("<<ComboboxSelected>>", lambda e: self.ok(), add="+")

    def _fit_error(self, event):
        wrap = max(120, min(self.box_width, event.width - 8))
        if self.err.cget("wraplength") != wrap:
            self.err.config(wraplength=wrap)

    def get(self):
        return self.box.get().strip()

    def set(self, value):
        self.box.set(value)

    def set_values(self, values):
        self.box.config(values=values)

    def error(self, msg):
        self.err.config(text="⚠ " + msg)

    def ok(self):
        self.err.config(text="")


def check_circle(parent, color=GREEN, fill=GREEN_L, size=100):
    c = tk.Canvas(parent, width=size, height=size, bg=CARD, highlightthickness=0)
    c.create_oval(4, 4, size - 4, size - 4, fill=fill, outline="")
    m = size / 2
    c.create_line(
        m - 16,
        m + 1,
        m - 4,
        m + 13,
        m + 18,
        m - 12,
        fill=color,
        width=4,
        capstyle="round",
        joinstyle="round",
    )
    return c


def cross_circle(parent, size=100):
    c = tk.Canvas(parent, width=size, height=size, bg=CARD, highlightthickness=0)
    c.create_oval(4, 4, size - 4, size - 4, fill="#FEE2E2", outline="")
    c.create_line(35, 35, 65, 65, fill=RED, width=4, capstyle="round")
    c.create_line(35, 65, 65, 35, fill=RED, width=4, capstyle="round")
    return c


# ======================================================================
# SECTION 6: MAIN APPLICATION AND PAGE NAVIGATION
# ======================================================================
# Import page mixins after the shared settings and widgets they use are defined.
from dashboard import DashboardMixin
from registration import RegistrationMixin
from user_management import UserManagementMixin


# App
class App(tk.Tk, DashboardMixin, RegistrationMixin, UserManagementMixin):
    def __init__(self):
        # Windows: give the app its own taskbar identity so the custom icon shows there too.
        if os.name == "nt":
            try:
                import ctypes

                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "sce.smartgate.app"
                )
            except Exception:
                pass
        super().__init__()
        self.option_add("*Font", f"{FONT} 11")
        self.title("Smart Gate - Samtse College of Education")
        # Window icon: the college logo (keep college_logo.png beside this script).
        # self.app_icon must stay on self, or Tk drops the picture and the icon disappears.
        here = os.path.dirname(os.path.abspath(__file__))
        png_path, ico_path = os.path.join(here, "college_logo.png"), os.path.join(
            here, "college_logo.ico"
        )
        try:
            logo = Image.open(png_path).convert("RGBA")
            # Windows title bars use a .ico best: build it once from the PNG if it is missing.
            if os.name == "nt" and not os.path.isfile(ico_path):
                logo.save(
                    ico_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)]
                )
            self.app_icon = ImageTk.PhotoImage(
                logo.resize((64, 64), Image.Resampling.LANCZOS)
            )
            self.iconphoto(True, self.app_icon)
        except Exception as e:
            print(
                "Window icon not set:", e
            )  # shows in the terminal; the app still opens
        if os.name == "nt" and os.path.isfile(ico_path):
            try:
                self.iconbitmap(ico_path)
            except tk.TclError:
                pass
        # Fit the available display instead of opening taller than smaller laptop screens.
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        start_w, start_h = min(1200, max(900, sw - 40)), min(820, max(620, sh - 80))
        self.geometry(f"{start_w}x{start_h}")
        self.minsize(min(900, max(760, sw - 40)), min(620, max(560, sh - 80)))
        self.configure(bg=BG)
        try:
            if os.name == "nt":
                self.state("zoomed")
        except tk.TclError:
            pass
        self.db = DB()
        self.engine = None  # the face models load in the background (see _load_engine)
        self.engine_error = None
        self.cam = None
        self.role = None
        self.me = None  # the signed-in staff member (sqlite Row)
        self.verified = None  # currently verified user (sqlite Row)
        self.clock_lbl = None
        self.current_page = "dashboard"
        self.jobs = []
        self.samples, self.capturing, self.last_cap = [], False, 0.0
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.style_ttk()
        # Show a loading screen at once, so the window never sits dark while the AI models load.
        self.show_splash()
        self.update()
        threading.Thread(target=self._load_engine, daemon=True).start()
        self._wait_engine()

    def show_splash(self):
        """Loading screen shown while YOLO and SFace start up."""
        self.clear()
        bg = tk.Frame(self, bg=NAVY)
        bg.pack(fill="both", expand=True)
        mid = tk.Frame(bg, bg=NAVY)
        mid.place(relx=0.5, rely=0.5, anchor="center")
        icon = getattr(self, "app_icon", None)
        if icon is not None:
            tk.Label(mid, image=icon, bg=NAVY).pack(pady=(0, 14))
        tk.Label(mid, text="Smart Gate", bg=NAVY, fg="white", font=F(28, "bold")).pack()
        tk.Label(
            mid, text="Samtse College of Education", bg=NAVY, fg="#A9C0D3", font=F(11)
        ).pack(pady=(2, 22))
        bar = ttk.Progressbar(mid, mode="indeterminate", length=260)
        bar.pack()
        bar.start(12)
        tk.Label(
            mid,
            text="Loading face recognition models… please wait",
            bg=NAVY,
            fg="#A9C0D3",
            font=F(9),
        ).pack(pady=(12, 0))

    def _load_engine(self):
        """Runs on a background thread: load YOLO + SFace and warm them up."""
        try:
            eng = FaceEngine()
            try:  # first use of a model is slow, so do it now
                eng.yolo.predict(
                    np.zeros((480, 640, 3), np.uint8), imgsz=YOLO_SIZE, verbose=False
                )
                eng.embed(np.zeros((112, 112, 3), np.uint8))
            except Exception:
                pass
            self.engine = eng  # set last: the main thread watches for this
        except Exception as e:
            self.engine_error = e

    def _wait_engine(self):
        """Main thread: when the models are ready, open the login (or first-time setup) page."""
        if self.engine is None and self.engine_error is None:
            self.after(100, self._wait_engine)
            return
        if self.engine_error is not None:
            messagebox.showerror(
                "Face models could not start",
                f"{self.engine_error}\n\nCheck the files in the models folder, "
                "then start the app again.",
                parent=self,
            )
            self.destroy()
            return
        # Show the login page when staff accounts already exist. The first run
        # opens the initial System Administrator setup form instead.
        self.show_welcome()

    def on_close(self):
        self.stop_camera()
        self.destroy()

    def style_ttk(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(
            "Treeview",
            rowheight=44,
            font=F(9),
            background=CARD,
            fieldbackground=CARD,
            borderwidth=0,
            foreground=INK,
        )
        s.configure(
            "Treeview.Heading",
            font=F(8, "bold"),
            background=BG,
            foreground=MUTED,
            relief="flat",
            padding=8,
        )
        s.map(
            "Treeview",
            background=[("selected", "#EAF3FB")],
            foreground=[("selected", INK)],
        )
        s.configure("TCombobox", fieldbackground=FIELD, padding=6)
        s.configure(
            "Horizontal.TProgressbar",
            troughcolor=FIELD,
            background=GREEN,
            bordercolor=BORDER,
            lightcolor=GREEN,
            darkcolor=GREEN,
        )

    # Helpers
    def clear(self, widget=None):
        for j in self.jobs:
            try:
                self.after_cancel(j)
            except tk.TclError:
                pass
        self.jobs = []
        for w in (widget or self).winfo_children():
            w.destroy()

    def later(self, ms, fn):
        j = self.after(ms, fn)
        self.jobs.append(j)
        return j

    def tick(self):
        try:
            if self.clock_lbl and self.clock_lbl.winfo_exists():
                self.clock_lbl.config(text=now().strftime("%I:%M:%S %p"))
            if getattr(self, "login_clock", None) and self.login_clock.winfo_exists():
                self.login_clock.config(text=now().strftime("%I:%M:%S %p"))
            if getattr(self, "login_date", None) and self.login_date.winfo_exists():
                self.login_date.config(text=now().strftime("%A, %d %B %Y"))
        except tk.TclError:
            pass
        self.after(1000, self.tick)

    # Camera helpers
    def start_camera(self):
        self.stop_camera()
        cam = Camera(CAMERA_INDEX)
        if not cam.running:
            cam.stop()
            return False
        self.cam = cam
        return True

    def stop_camera(self):
        if self.cam:
            self.cam.stop()
            self.cam = None

    def show_frame(self, label, frame, size):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        photo = ImageTk.PhotoImage(Image.fromarray(rgb).resize(size))
        label.configure(image=photo, text="")
        label.image = photo  # keep a reference or Tk drops the picture

    @staticmethod
    def draw_box(frame, box, color, text):
        x, y, w, h = box
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
        if text:
            cv2.putText(
                frame,
                text,
                (x, max(y - 8, 18)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
            )

    # ------------------------------------------------------------------
    # SECTION 6A: LOGIN AND FIRST-TIME SETUP
    # ------------------------------------------------------------------
    def auth_layout(self, width=400, rely=0.52):
        """Shared look of the sign-in and set-up screens. Returns the white card to fill.
        The card scrolls when the screen is too small, so no field or button is ever hidden.
        """
        self.stop_camera()
        self.role, self.me, self.verified = None, None, None
        self.clear()
        LB = "#BFE0FB"
        left = tk.Frame(self, bg=LB)
        right = tk.Frame(self, bg=NAVY, width=300)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        left.pack(side="left", fill="both", expand=True)

        # Official Samtse College of Education logo (keep college_logo.png beside this script).
        # Image loading is optional so the application can still open if the logo is missing.
        logo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "college_logo.png"
        )
        logo = tk.Frame(left, bg=LB)
        logo.place(x=40, y=22)
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_img.thumbnail((58, 62), Image.Resampling.LANCZOS)
            self.college_logo_photo = ImageTk.PhotoImage(logo_img)
            tk.Label(logo, image=self.college_logo_photo, bg=LB).pack(
                side="left", padx=(0, 10)
            )
        except Exception:
            tk.Label(
                logo,
                text="SCE",
                bg=PRIMARY,
                fg="white",
                font=F(13, "bold"),
                width=4,
                height=2,
            ).pack(side="left", padx=(0, 10))
        t = tk.Frame(logo, bg=LB)
        t.pack(side="left", anchor="center")
        tk.Label(
            t, text="SAMTSE COLLEGE OF EDUCATION", bg=LB, fg=PRIMARY, font=F(10, "bold")
        ).pack(anchor="w")
        tk.Label(
            t, text="SMARTGATE · SCE FACE RECOGNITION SYSTEM", bg=LB, fg=INK, font=F(8)
        ).pack(anchor="w", pady=(4, 0))

        # Scrollable white card: grows to its content, but never taller than the space
        # under the logo. A scrollbar appears only when the form does not fit.
        wrap = tk.Frame(left, bg=LB)
        cv = tk.Canvas(wrap, bg=LB, highlightthickness=0, width=width)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left")
        box = tk.Frame(
            cv,
            bg=CARD,
            padx=26,
            pady=18,
            highlightthickness=1,
            highlightbackground="#9CC9EC",
        )
        cv.create_window((0, 0), window=box, anchor="nw", width=width)

        def fit(_e=None):
            need = box.winfo_reqheight()
            avail = max(left.winfo_height() - 130, 240)
            cv.configure(height=min(need, avail), scrollregion=(0, 0, width, need))
            if need > avail:
                sb.pack(side="right", fill="y")
            else:
                sb.pack_forget()

        box.bind("<Configure>", fit)
        left.bind("<Configure>", fit)
        box.bind(
            "<Enter>",
            lambda e: cv.bind_all(
                "<MouseWheel>",
                lambda ev: cv.yview_scroll(int(-ev.delta / 120), "units"),
            ),
        )
        box.bind("<Leave>", lambda e: cv.unbind_all("<MouseWheel>"))
        wrap.place(relx=0.5, rely=rely, anchor="center")

        tk.Label(
            left,
            text="© 2026 Samtse College of Education. All rights reserved.",
            bg=LB,
            fg=INK,
            font=F(8),
            anchor="center",
        ).place(relx=0.5, rely=0.975, anchor="center")
        back = tk.Label(
            left,
            text="\u2190 Back to Home",
            bg=LB,
            fg=PRIMARY,
            font=F(9, "bold"),
            cursor="hand2",
            padx=8,
            pady=5,
        )
        back.place(relx=1.0, x=-24, y=24, anchor="ne")
        back.bind("<Enter>", lambda e: back.config(bg="#EAF3FB", fg=PRIMARY_D))
        back.bind("<Leave>", lambda e: back.config(bg=LB, fg=PRIMARY))
        back.bind(
            "<ButtonPress-1>", lambda e: back.config(bg="#DCEBFA", fg="#D97706")
        )
        back.bind("<ButtonRelease-1>", lambda e: self.show_welcome())

        clock = tk.Frame(right, bg=NAVY)
        clock.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(
            clock,
            text="SAMTSE COLLEGE OF EDUCATION",
            bg=NAVY,
            fg="#A9C0D3",
            font=F(8, "bold"),
        ).pack(pady=(0, 14))
        tk.Label(
            clock,
            text="LOCAL TIME",
            bg=NAVY,
            fg="#A9C0D3",
            font=F(8, "bold"),
        ).pack(pady=(0, 5))
        self.login_clock = tk.Label(
            clock,
            text=now().strftime("%I:%M:%S %p"),
            bg=NAVY,
            fg="white",
            font=F(24, "bold"),
        )
        self.login_clock.pack()
        self.login_date = tk.Label(
            clock,
            text=now().strftime("%A, %d %B %Y"),
            bg=NAVY,
            fg="#DCE8F3",
            font=F(9),
        )
        self.login_date.pack(pady=(8, 0))
        tk.Frame(clock, bg="#42607D", height=1, width=190).pack(pady=18)
        tk.Label(
            clock,
            text="BHUTAN STANDARD TIME  ·  UTC+06:00",
            bg=NAVY,
            fg="#A9C0D3",
            font=F(7, "bold"),
        ).pack()
        if not getattr(self, "_ticking", False):
            self._ticking = True
            self.tick()
        return box

    def start_session(self, row):
        self.me = row
        self.role = row["role"]
        self.login_time = now()
        self.db.touch_login(row["username"])
        self.build_shell()
        # Every role lands on the dashboard after login. Registration is opened
        # only when the user selects Student Registration from the navigation.
        self.navigate("dashboard")

    # ------------------------------------------------------------------
    # SECTION 6B: SHARED FIELD VALIDATION / FORM HELPERS
    # ------------------------------------------------------------------
    # Field rules shared by the screens and dialogs
    def msg_username(self, v):
        m = username_problem(v)
        if m:
            return m
        if self.db.staff_get(v):
            return "This username is already taken."
        return ""

    @staticmethod
    def msg_password(v):
        return password_problem(v)

    def msg_staff_email(self, v, current=None):
        """Recovery email check for staff accounts. `current` = the account being edited."""
        v = v.lower()
        if not v:
            return "Email address is required."
        if not re.fullmatch(
            r"[a-z0-9._%+\-]+@[a-z0-9\-]+(\.[a-z0-9\-]+)*\.[a-z]{2,}", v
        ):
            return "Enter a valid email address, e.g. name@gmail.com."
        other = self.db.staff_by_email(v)
        if other and other["username"] != current:
            return "This email is already used by another staff account."
        return ""

    def show_setup(self):
        """Responsive, compact first-page sign-up card with a separate Log in route."""
        first_setup = self.db.staff_count() == 0
        box = self.auth_layout(510, 0.52)
        box.configure(padx=24, pady=16)

        tk.Label(
            box, text="Create your account", bg=CARD, fg=INK, font=F(19, "bold")
        ).pack(anchor="w")
        if first_setup:
            intro = (
                "Set up Smart Gate by creating the first System Administrator account. "
                "You can add College Management and Security Guard accounts afterwards."
            )
        else:
            intro = (
                "Smart Gate is already set up. Sign-up is reserved for initial setup; "
                "only System Administrator and College Management accounts can create staff accounts."
            )
        tk.Label(
            box,
            text=intro,
            bg=CARD,
            fg=MUTED,
            font=F(8),
            justify="left",
            wraplength=450,
        ).pack(anchor="w", pady=(3, 7))

        # A two-column field layout keeps the complete form visible on typical laptop screens.
        fields = tk.Frame(box, bg=CARD)
        fields.pack(fill="x")
        fields.grid_columnconfigure(0, weight=1, uniform="signup")
        fields.grid_columnconfigure(1, weight=1, uniform="signup")
        f_name = FormField(fields, "Full Name", wrap=210)
        f_user = FormField(fields, "Username", hint="e.g. tashi.admin", wrap=210)
        f_pw = FormField(
            fields, "Password", show="•", hint="8+ chars, letters + numbers", wrap=210
        )
        f_pw2 = FormField(fields, "Confirm Password", show="•", wrap=210)
        f_email = FormField(
            fields,
            "Email (for password recovery)",
            hint="e.g. name@gmail.com",
            wrap=450,
        )
        f_name.grid(row=0, column=0, sticky="ew", padx=(0, 9), pady=(0, 1))
        f_user.grid(row=0, column=1, sticky="ew", padx=(9, 0), pady=(0, 1))
        f_pw.grid(row=1, column=0, sticky="ew", padx=(0, 9), pady=(0, 1))
        f_pw2.grid(row=1, column=1, sticky="ew", padx=(9, 0), pady=(0, 1))
        f_email.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 1))

        confirm_msg = lambda v: (
            "Type the password again."
            if not v
            else "" if v == f_pw.entry.get().strip() else "Passwords do not match."
        )
        f_name.live(self.msg_name)
        f_user.live(lambda v: self.msg_username(v.lower()))
        f_pw.live(password_problem, lambda: f_pw2.check_now() if f_pw2.get() else None)
        f_pw2.live(confirm_msg)
        f_email.live(self.msg_staff_email)
        msg = tk.Label(
            box, text="", bg=CARD, fg=RED, font=F(8), wraplength=450, justify="left"
        )
        msg.pack(anchor="w", pady=(3, 2))

        def create():
            # Public staff-account creation is blocked after the first administrator exists.
            if self.db.staff_count() > 0:
                messagebox.showwarning(
                    "Sign-up unavailable",
                    "The initial System Administrator account has already been created.\n\n"
                    "For security, only System Administrator and College Management accounts "
                    "can create staff accounts. "
                    "Click Log in to continue.",
                    parent=self,
                )
                return
            ok = True
            for f, fn in (
                (f_name, self.msg_name),
                (f_user, lambda v: self.msg_username(v.lower())),
                (f_pw, password_problem),
                (f_pw2, confirm_msg),
                (f_email, self.msg_staff_email),
            ):
                error = fn(f.get())
                if error:
                    f.error(error)
                    ok = False
                else:
                    f.good()
            if not ok:
                msg.config(text="Please check the highlighted fields.")
                return
            name = " ".join(w[:1].upper() + w[1:] for w in f_name.get().split())
            self.db.add_staff(
                f_user.get().lower(),
                name,
                "System Administrator",
                f_pw.get(),
                f_email.get().lower(),
            )
            messagebox.showinfo(
                "Account created",
                f"System Administrator account created.\n\nUsername: {f_user.get().lower()}\n"
                "Keep your password safe; it cannot be displayed again.",
                parent=self,
            )
            self.start_session(self.db.staff_get(f_user.get()))

        Btn(
            box,
            "Create System Administrator account" if first_setup else "Sign up",
            create,
        ).pack(fill="x", pady=(3, 0), ipady=1)

        login_row = tk.Frame(box, bg=CARD)
        login_row.pack(fill="x", pady=(7, 0))
        tk.Label(
            login_row, text="Already have an account?", bg=CARD, fg=MUTED, font=F(8)
        ).pack(side="left")

        def open_login():
            if self.db.staff_count() > 0:
                self.show_login()
            else:
                messagebox.showinfo(
                    "Create the first account first",
                    "No account exists yet. Create the first System Administrator account before logging in.",
                    parent=self,
                )

        Btn(login_row, "Log in", open_login, style="outline").pack(
            side="right", ipadx=12
        )
        f_name.bind_return(f_user.focus)
        f_user.bind_return(f_pw.focus)
        f_pw.bind_return(f_pw2.focus)
        f_pw2.bind_return(f_email.focus)
        f_email.bind_return(create)
        f_name.focus()

    # ------------------------------------------------------------------
    # WELCOME SCREEN (first page: campus photo + navy panel + Login / About)
    # ------------------------------------------------------------------
    def show_welcome(self):
        self.stop_camera()
        self.role, self.me, self.verified = None, None, None
        self.clear()
        try:
            original = Image.open(os.path.join(BASE_DIR, "assets", "sce_campus.jpg")).convert("RGB")
        except Exception as e:
            print("Campus picture not loaded:", e)
            return self.show_setup() if self.db.staff_count() == 0 else self.show_login()
        try:
            logo_src = Image.open(os.path.join(BASE_DIR, "college_logo.png")).convert("RGBA")
        except Exception:
            logo_src = None
 
        cv = tk.Canvas(self, bg="#0B2A4A", highlightthickness=0, bd=0)
        cv.pack(fill="both", expand=True)
        YELLOW, DARK = "#FACC15", "#0B2A4A"
 
        def pill(x0, y0, x1, y1, **kw):
            r = (y1 - y0) / 2
            pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y1,
                   x1 - r, y1, x0 + r, y1, x0, y1, x0, y0]
            return cv.create_polygon(pts, smooth=True, **kw)
 
        def button(cx, cy, bw, bh, text, tag, fill, hover, outline, fs, command):
            shape = pill(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2,
                         fill=fill, outline=outline, width=2, tags=(tag,))
            cv.create_text(cx, cy, text=text, fill="white", font=F(fs, "bold"), tags=(tag,))
            cv.tag_bind(tag, "<Enter>", lambda e: (cv.itemconfig(shape, fill=hover),
                                                    cv.config(cursor="hand2")))
            cv.tag_bind(tag, "<Leave>", lambda e: (cv.itemconfig(shape, fill=fill),
                                                    cv.config(cursor="")))
            cv.tag_bind(tag, "<Button-1>", lambda e: command())
 
        def open_login():
            if self.db.staff_count() == 0:
                self.show_setup()
            else:
                self.show_login()
 
        def draw(_e=None):
            w, h = cv.winfo_width(), cv.winfo_height()
            if w < 50 or h < 50:
                return
            # photo fills the window, then a navy fade covers the right side
            s = max(w / original.width, h / original.height)
            img = original.resize((int(original.width * s) + 1, int(original.height * s) + 1),
                                  Image.Resampling.LANCZOS)
            l, t = (img.width - w) // 2, (img.height - h) // 2
            img = img.crop((l, t, l + w, t + h))
            a = np.clip((np.linspace(0, 1, w) - 0.30) / 0.32, 0, 1) * 0.93
            mask = Image.fromarray((np.tile(a, (h, 1)) * 255).astype("uint8"))
            img = Image.composite(Image.new("RGB", (w, h), (11, 42, 74)), img, mask)
            self.welcome_bg = ImageTk.PhotoImage(img)
            cv.delete("all")
            cv.create_image(0, 0, image=self.welcome_bg, anchor="nw")
 
            cx = int(w * 0.74)
            fs = lambda k: max(8, int(h * k))
            if logo_src is not None:
                lg = logo_src.copy()
                lg.thumbnail((int(h * 0.20), int(h * 0.20)), Image.Resampling.LANCZOS)
                self.welcome_logo = ImageTk.PhotoImage(lg)
                cv.create_image(cx, int(h * 0.15), image=self.welcome_logo)
            cv.create_text(cx, int(h * 0.31), text="SAMTSE COLLEGE OF EDUCATION",
                           fill="white", font=("Georgia", fs(0.030), "bold"))
            cv.create_line(cx - w * 0.17, h * 0.355, cx + w * 0.17, h * 0.355, fill="#7F96AC")
            cv.create_text(cx, int(h * 0.40), text="Learn  \u2022  Teach  \u2022  Empower",
                           fill="#DCE8F3", font=("Georgia", fs(0.026), "italic"))
            import tkinter.font as tkfont

            brand_size = max(8, min(fs(0.075), int(w * 0.055)))
            brand_font = tkfont.Font(
                self, family=FONT, size=brand_size, weight="bold"
            )
            sce_width = brand_font.measure("SCE")
            gate_width = brand_font.measure("SMARTGATE")
            gap = max(12, int(brand_size * 0.28))
            brand_width = sce_width + gap + gate_width
            available_width = w * 0.46
            if brand_width > available_width:
                brand_size = max(
                    8, int(brand_size * available_width / brand_width)
                )
                brand_font = tkfont.Font(
                    self, family=FONT, size=brand_size, weight="bold"
                )
                sce_width = brand_font.measure("SCE")
                gate_width = brand_font.measure("SMARTGATE")
                gap = max(12, int(brand_size * 0.28))
                brand_width = sce_width + gap + gate_width
            self.welcome_brand_font = brand_font
            brand_left = cx - brand_width / 2
            brand_y = int(h * 0.52)
            cv.create_text(brand_left + sce_width / 2, brand_y, text="SCE",
                           fill="white", font=brand_font)
            cv.create_text(
                brand_left + sce_width + gap + gate_width / 2,
                brand_y,
                text="SMARTGATE",
                fill=YELLOW,
                font=brand_font,
            )
            cv.create_text(cx, int(h * 0.605), text="Smart Face Recognition Entry & Exit System",
                           fill="white", font=(FONT, fs(0.026), "bold italic"))
            badge_text = "Secure Campus Access"
            badge_size = max(8, fs(0.022))
            badge_font = tkfont.Font(
                self, family=FONT, size=badge_size, weight="bold"
            )
            badge_pad = max(18, int(badge_size * 1.15))
            max_badge_width = w * 0.44
            text_width = badge_font.measure(badge_text)
            if text_width + 2 * badge_pad > max_badge_width:
                badge_size = max(
                    8,
                    int(
                        badge_size
                        * (max_badge_width - 2 * badge_pad)
                        / text_width
                    ),
                )
                badge_font = tkfont.Font(
                    self, family=FONT, size=badge_size, weight="bold"
                )
                text_width = badge_font.measure(badge_text)
            badge_width = min(max_badge_width, text_width + 2 * badge_pad)
            badge_height = max(36, int(h * 0.06))
            badge_center_y = h * 0.695
            pill(
                cx - badge_width / 2,
                badge_center_y - badge_height / 2,
                cx + badge_width / 2,
                badge_center_y + badge_height / 2,
                fill="#0F5132",
                outline=GREEN,
                width=2,
            )
            cv.create_text(
                cx,
                badge_center_y,
                text=badge_text,
                fill="white",
                font=badge_font,
            )
            bw, bh = int(w * 0.14), int(h * 0.075)
            button(cx - bw * 0.58, h * 0.80, bw, bh, "Login", "login",
                   PRIMARY, PRIMARY_D, "#4FA3E0", fs(0.024), open_login)
            button(cx + bw * 0.58, h * 0.80, bw, bh, "About", "about",
                   DARK, NAVY_ACTIVE, "white", fs(0.024), self.show_about)
            cv.create_text(cx, h * 0.955, text="\u00a9 2026 Samtse College of Education",
                           fill="#A9C0D3", font=("Georgia", fs(0.018), "italic"))
 
        cv.bind("<Configure>", draw)
 
    def show_about(self):
        import webbrowser

        self.stop_camera()
        self.role, self.me, self.verified = None, None, None
        self.clear()

        page = tk.Frame(self, bg="#F1F5F9")
        page.pack(fill="both", expand=True)
        hero = tk.Frame(page, bg=NAVY, height=184)
        hero.pack(fill="x")
        hero.pack_propagate(False)

        top = tk.Frame(hero, bg=NAVY)
        top.pack(fill="x", padx=30, pady=14)
        back = tk.Label(
            top,
            text="\u2190 Back to Home",
            bg=NAVY,
            fg="#DCE8F3",
            font=F(9, "bold"),
            cursor="hand2",
        )
        back.pack(side="left", pady=8, padx=8)
        back.bind("<ButtonRelease-1>", lambda _event: self.show_welcome())
        back.bind(
            "<ButtonPress-1>",
            lambda _event: back.config(bg="#294B6A", fg="#FACC15"),
        )
        back.bind(
            "<Enter>", lambda _event: back.config(bg=NAVY_ACTIVE, fg="white")
        )
        back.bind(
            "<Leave>", lambda _event: back.config(bg=NAVY, fg="#DCE8F3")
        )

        identity = tk.Frame(top, bg=NAVY)
        identity.pack(side="right")
        try:
            logo = Image.open(os.path.join(BASE_DIR, "college_logo.png")).convert(
                "RGBA"
            )
            logo.thumbnail((42, 42), Image.Resampling.LANCZOS)
            self.about_logo = ImageTk.PhotoImage(logo)
            tk.Label(identity, image=self.about_logo, bg=NAVY).pack(
                side="left", padx=(0, 10)
            )
        except (OSError, tk.TclError):
            pass
        tk.Label(
            identity,
            text="SCE  |  SMARTGATE",
            bg=NAVY,
            fg="white",
            font=F(9, "bold"),
        ).pack(side="left")

        tk.Label(
            hero,
            text="Samtse College of Education",
            bg=NAVY,
            fg="white",
            font=("Georgia", 25, "bold"),
        ).pack(anchor="center", pady=(0, 5))
        tk.Label(
            hero,
            text="A tradition of teacher education  \u2022  Samtse, Bhutan",
            bg=NAVY,
            fg="#B9D2E8",
            font=("Georgia", 11, "italic"),
        ).pack(anchor="center")
        tk.Frame(hero, bg="#FACC15", height=3).pack(side="bottom", fill="x")

        body = tk.Frame(page, bg="#F1F5F9")
        body.pack(fill="both", expand=True)
        canvas = tk.Canvas(body, bg="#F1F5F9", highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        content = tk.Frame(canvas, bg="#F1F5F9")
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")

        def resize_content(event):
            canvas.itemconfigure(content_window, width=event.width)

        def update_scroll(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            needs_scroll = content.winfo_reqheight() > canvas.winfo_height()
            if needs_scroll and not scrollbar.winfo_ismapped():
                scrollbar.pack(side="right", fill="y")
            elif not needs_scroll and scrollbar.winfo_ismapped():
                scrollbar.pack_forget()

        canvas.bind("<Configure>", resize_content)
        content.bind("<Configure>", update_scroll)
        content.bind(
            "<Enter>",
            lambda _event: canvas.bind_all(
                "<MouseWheel>",
                lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"),
            ),
        )
        content.bind("<Leave>", lambda _event: canvas.unbind_all("<MouseWheel>"))

        inner = tk.Frame(content, bg="#F1F5F9")
        inner.pack(fill="both", padx=42, pady=26)
        campus_banner = tk.Canvas(
            inner, bg=NAVY, height=250, highlightthickness=0, bd=0
        )
        campus_banner.pack(fill="x", pady=(0, 20))
        try:
            campus_source = Image.open(
                os.path.join(BASE_DIR, "assets", "sce_about.jpg")
            ).convert("RGB")
        except OSError as error:
            print("About page campus photo not loaded:", error)
            campus_source = None
        if campus_source is not None:
            campus_source.thumbnail((1800, 1200), Image.Resampling.LANCZOS)
        banner_image = campus_banner.create_image(0, 0, anchor="center")
        banner_panel = campus_banner.create_rectangle(
            1, 1, 2, 2, fill="#173B5B", outline=""
        )
        banner_accent = campus_banner.create_rectangle(
            1, 1, 3, 2, fill="#FACC15", outline=""
        )
        banner_kicker = campus_banner.create_text(
            1,
            1,
            anchor="nw",
            text="SAMTSE  \u2022  BHUTAN",
            fill="#FACC15",
            font=F(9, "bold"),
        )
        banner_title = campus_banner.create_text(
            1,
            1,
            anchor="nw",
            width=300,
            text="A place for\nlearning",
            fill="white",
            font=("Georgia", 24, "bold"),
            justify="left",
        )
        banner_caption = campus_banner.create_text(
            1,
            1,
            anchor="nw",
            width=300,
            text="Samtse College of Education\nA view of the campus",
            fill="#E2E8F0",
            font=F(10),
            justify="left",
        )

        def draw_campus_banner(event):
            width, height = max(event.width, 1), max(event.height, 1)
            photo_area = int(width * 0.48)
            photo_pad = 18
            if campus_source is not None:
                max_photo_width = max(1, photo_area - photo_pad * 2)
                max_photo_height = max(1, height - photo_pad * 2)
                scale = min(
                    max_photo_width / campus_source.width,
                    max_photo_height / campus_source.height,
                )
                resized = campus_source.resize(
                    (
                        max(1, int(campus_source.width * scale)),
                        max(1, int(campus_source.height * scale)),
                    ),
                    Image.Resampling.LANCZOS,
                )
                self.about_campus_photo = ImageTk.PhotoImage(resized)
                campus_banner.itemconfigure(
                    banner_image, image=self.about_campus_photo
                )
                campus_banner.coords(
                    banner_image,
                    photo_area / 2,
                    height / 2,
                )
            text_left = photo_area + 28
            text_width = max(100, width - text_left - 22)
            campus_banner.coords(banner_panel, photo_area, 0, width, height)
            campus_banner.coords(banner_accent, photo_area, 0, photo_area + 4, height)
            campus_banner.coords(banner_kicker, text_left, height * 0.24)
            campus_banner.coords(banner_title, text_left, height * 0.38)
            campus_banner.itemconfigure(banner_title, width=text_width)
            campus_banner.coords(banner_caption, text_left, height * 0.72)
            campus_banner.itemconfigure(banner_caption, width=text_width)

        campus_banner.bind("<Configure>", draw_campus_banner)

        intro = card(inner, padx=24, pady=20)
        intro.pack(fill="x", pady=(0, 20))
        tk.Label(
            intro, text="OUR COLLEGE", bg=CARD, fg=PRIMARY, font=F(8, "bold")
        ).pack(anchor="w", pady=(0, 5))
        tk.Label(
            intro,
            text="Education that shapes the future",
            bg=CARD,
            fg=INK,
            font=("Georgia", 20, "bold"),
        ).pack(anchor="w")
        intro_copy = tk.Label(
            intro,
            text=(
                "Samtse College of Education (SCE), located in Samtse, Bhutan, "
                "is dedicated to education. The College contributes to the "
                "development of educators and to learning through teaching, "
                "research and service."
            ),
            bg=CARD,
            fg=MUTED,
            font=F(11),
            justify="left",
            wraplength=900,
        )
        intro_copy.pack(anchor="w", fill="x", pady=(8, 0))

        overview = tk.Frame(inner, bg="#F1F5F9")
        overview.pack(fill="x", pady=(0, 20))
        overview.grid_columnconfigure((0, 1), weight=1, uniform="overview")

        purpose = card(overview, padx=20, pady=18)
        purpose.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(
            purpose,
            text="A LEGACY IN TEACHER EDUCATION",
            bg=CARD,
            fg=PRIMARY,
            font=F(9, "bold"),
        ).pack(anchor="w")
        purpose_copy = tk.Label(
            purpose,
            text=(
                "Founded by Bhutan's Third Dharma King, Late His Majesty Jigme "
                "Dorji Wangchuck, SCE began as the Teacher Training Institute on "
                "29 May 1968 with 41 students. Since then, it has contributed "
                "more than 5,000 graduates to Bhutan's education system."
            ),
            bg=CARD,
            fg=INK,
            font=F(11),
            justify="left",
            wraplength=420,
        )
        purpose_copy.pack(anchor="w", fill="x", pady=(8, 0))

        pathways = card(overview, padx=20, pady=18)
        pathways.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(
            pathways,
            text="VISION",
            bg=CARD,
            fg=PRIMARY,
            font=F(9, "bold"),
        ).pack(anchor="w")
        pathway_intro = tk.Label(
            pathways,
            text="A center of excellence committed to research and innovation in Education.",
            bg=CARD,
            fg=INK,
            font=("Georgia", 14, "bold"),
            justify="left",
            wraplength=420,
        )
        pathway_intro.pack(anchor="w", fill="x", pady=(8, 12))
        pathway_list = tk.Label(
            pathways,
            text=(
                "The College's approach is inspired by right view, right "
                "contemplation and right action, working together toward "
                "meaningful outcomes."
            ),
            bg=CARD,
            fg=MUTED,
            font=F(9),
            justify="left",
            wraplength=420,
        )
        pathway_list.pack(anchor="w", fill="x")

        tk.Label(
            inner,
            text="THE COLLEGE'S CONTRIBUTION",
            bg="#F1F5F9",
            fg=INK,
            font=F(10, "bold"),
        ).pack(anchor="w", pady=(0, 10))
        pillars = tk.Frame(inner, bg="#F1F5F9")
        pillars.pack(fill="x", pady=(0, 18))
        pillar_data = (
            (
                "01",
                "Teacher education",
                "Preparing educators with the knowledge and skills to guide learning.",
                PRIMARY,
            ),
            (
                "02",
                "Teaching & learning",
                "Encouraging thoughtful teaching and positive learning experiences.",
                GREEN,
            ),
            (
                "03",
                "Research & service",
                "Learning from inquiry and contributing through service to education.",
                "#D97706",
            ),
        )
        pillar_cards = []
        for index, (number, title, description, accent) in enumerate(pillar_data):
            item = card(pillars, padx=17, pady=15)
            item.grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(0, 10) if index < 2 else 0,
            )
            tk.Frame(item, bg=accent, height=3).pack(fill="x", pady=(0, 12))
            tk.Label(item, text=number, bg=CARD, fg=accent, font=F(8, "bold")).pack(
                anchor="w"
            )
            tk.Label(
                item, text=title, bg=CARD, fg=INK, font=("Georgia", 13, "bold")
            ).pack(anchor="w", pady=(5, 4))
            detail = tk.Label(
                item,
                text=description,
                bg=CARD,
                fg=MUTED,
                font=F(10),
                justify="left",
                wraplength=250,
            )
            detail.pack(anchor="w", fill="x")
            pillar_cards.append(detail)
        for index in range(3):
            pillars.grid_columnconfigure(index, weight=1, uniform="pillar")

        programs = card(inner, padx=22, pady=18)
        programs.pack(fill="x", pady=(0, 18))
        tk.Label(
            programs,
            text="ACADEMIC PROGRAMMES & AREAS",
            bg=CARD,
            fg=PRIMARY,
            font=F(9, "bold"),
        ).pack(anchor="w")
        programs_copy = tk.Label(
            programs,
            text=(
                "SCE describes its current offerings across bachelor's, diploma, "
                "postgraduate and master's levels. Its teacher-education and related "
                "fields include science and mathematics, contemplative counselling, "
                "social sciences and humanities, language and literary education, "
                "information technology, and commerce and business education. "
                "Please consult the College's official website for current programme "
                "names, admission requirements and availability."
            ),
            bg=CARD,
            fg=INK,
            font=F(11),
            justify="left",
            wraplength=900,
        )
        programs_copy.pack(anchor="w", fill="x", pady=(8, 0))

        mission = card(inner, padx=22, pady=18)
        mission.pack(fill="x", pady=(0, 18))
        tk.Label(
            mission,
            text="THE COLLEGE'S MISSION",
            bg=CARD,
            fg=PRIMARY,
            font=F(9, "bold"),
        ).pack(anchor="w")
        mission_copy = tk.Label(
            mission,
            text=(
                "SCE's mission includes offering relevant teacher education and "
                "research; preparing high-quality secondary STEM teachers; "
                "supporting lifelong professional learning; contributing research "
                "and policy advice; and building collaborations that encourage "
                "innovation in education."
            ),
            bg=CARD,
            fg=INK,
            font=F(11),
            justify="left",
            wraplength=900,
        )
        mission_copy.pack(anchor="w", fill="x", pady=(8, 0))

        smartgate = tk.Frame(inner, bg=NAVY, padx=20, pady=16)
        smartgate.pack(fill="x")
        tk.Label(
            smartgate, text="SMARTGATE", bg=NAVY, fg="#FACC15", font=F(9, "bold")
        ).pack(anchor="w")
        smartgate_copy = tk.Label(
            smartgate,
            text=(
                "SmartGate supports campus entry and exit management for authorized "
                "staff, with face verification and access-record features."
            ),
            bg=NAVY,
            fg="#E2E8F0",
            font=F(10),
            justify="left",
            wraplength=900,
        )
        smartgate_copy.pack(anchor="w", fill="x", pady=(5, 0))

        source_link = tk.Label(
            inner,
            text="College history and programme information  \u2022  SCE official website",
            bg="#F1F5F9",
            fg=PRIMARY,
            font=F(8, "underline"),
            cursor="hand2",
        )
        source_link.pack(pady=(16, 3))
        source_link.bind(
            "<Button-1>",
            lambda _event: webbrowser.open("https://www.sce.edu.bt/about-us-2/"),
        )
        tk.Label(
            inner,
            text="\u00a9 2026 Samtse College of Education",
            bg="#F1F5F9",
            fg=MUTED,
            font=F(8),
        ).pack(pady=(0, 0))

        def update_text_widths(event):
            width = max(180, event.width - 100)
            intro_copy.config(wraplength=width)
            smartgate_copy.config(wraplength=width)
            overview_width = max(150, int((event.width - 84) / 2) - 64)
            purpose_copy.config(wraplength=overview_width)
            pathway_intro.config(wraplength=overview_width)
            pathway_list.config(wraplength=overview_width)
            programs_copy.config(wraplength=width)
            mission_copy.config(wraplength=width)
            pillar_width = max(140, int((event.width - 120) / 3) - 38)
            for detail in pillar_cards:
                detail.config(wraplength=pillar_width)

        content.bind("<Configure>", update_text_widths, add="+")
 
    def show_login(self):
        if self.db.staff_count() == 0:
            return self.show_setup()
        box = self.auth_layout(420)
        tk.Label(
            box,
            text="SECURE STAFF ACCESS",
            bg="#EAF3FB",
            fg=PRIMARY,
            font=F(8, "bold"),
            padx=9,
            pady=4,
        ).pack(anchor="w", pady=(0, 10))
        tk.Label(box, text="Welcome back", bg=CARD, fg=INK, font=F(21, "bold")).pack(
            anchor="w", pady=(0, 2)
        )
        tk.Label(
            box,
            text="Sign in with your staff account to continue.",
            bg=CARD,
            fg=MUTED,
            font=F(9),
        ).pack(anchor="w", pady=(0, 8))
        tk.Frame(box, bg=BORDER, height=1).pack(fill="x", pady=(0, 5))
        self.e_user = FormField(box, "Username", hint="Your staff username", wrap=350)
        self.e_user.pack(fill="x", pady=(0, 2))
        self.e_pass = FormField(
            box, "Password", show="•", hint="Your account password", wrap=350
        )
        self.e_pass.pack(fill="x", pady=(0, 2))
        self.login_msg = tk.Label(
            box, text="", bg=CARD, fg=RED, font=F(8), wraplength=350, justify="left"
        )
        self.login_msg.pack(anchor="w", fill="x", pady=(5, 0))
        self.login_btn = Btn(box, "Log in", self.do_login)
        self.login_btn.pack(fill="x", pady=(10, 0), ipady=1)

        tk.Label(
            box,
            text="Need access? Contact your system administrator.",
            bg=CARD,
            fg=MUTED,
            font=F(8),
            wraplength=350,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))

        fg = tk.Label(
            box,
            text="Forgot your password?",
            bg=CARD,
            fg=PRIMARY,
            font=F(8, "bold"),
            cursor="hand2",
        )
        fg.pack(anchor="w", pady=(10, 0))
        fg.bind("<Button-1>", lambda e: self.recover_dialog())
        self.e_user.live(
            lambda value: (
                "Username is required."
                if not value
                else username_problem(value.lower())
            )
        )
        self.e_pass.live(
            lambda value: "Password is required." if not value else ""
        )

        def clear_login_feedback(_event=None):
            self.login_msg.config(text="")

        self.e_user.entry.bind("<KeyRelease>", clear_login_feedback, add="+")
        self.e_pass.entry.bind("<KeyRelease>", clear_login_feedback, add="+")
        self.e_pass.bind_return(self.do_login)
        self.e_user.bind_return(self.e_pass.focus)
        self.e_user.focus()

    def recover_dialog(self):
        """Forgot password: a 6-digit code is emailed to the administrator's email."""
        top = self.popup(
            "Recover password",
            "System Administrator and College Management accounts can use this feature.",
            470,
            600,
        )
        cd = card(top.content, padx=24, pady=10)
        cd.pack(fill="x", padx=22)
        f_id = FormField(cd, "Username or email", wrap=380)
        f_id.pack(fill="x")
        msg = tk.Label(
            cd, text="", bg=CARD, fg=MUTED, font=F(8), wraplength=380, justify="left"
        )
        msg.pack(anchor="w", pady=(4, 0))
        state = {"row": None, "hash": None, "expires": 0.0, "tries": 0}
        step2 = tk.Frame(cd, bg=CARD)
        f_code = FormField(step2, "6-digit code", wrap=380)
        f_pw = FormField(
            step2,
            "New Password",
            show="•",
            hint="8+ characters, letters and numbers",
            wrap=380,
        )
        f_pw2 = FormField(step2, "Confirm New Password", show="•", wrap=380)
        for f in (f_code, f_pw, f_pw2):
            f.pack(fill="x")
        confirm_msg = lambda v: (
            "Type the password again."
            if not v
            else "" if v == f_pw.entry.get().strip() else "Passwords do not match."
        )
        f_pw.live(password_problem, lambda: f_pw2.check_now() if f_pw2.get() else None)
        f_pw2.live(confirm_msg)

        def send():
            ident = f_id.get().lower()
            if not ident:
                f_id.error("Enter your username or email.")
                return
            if not (SENDER_EMAIL and SENDER_APP_PASSWORD):
                msg.config(
                    fg=RED,
                    text="Email sending is not set up yet. Fill SENDER_EMAIL and "
                    "SENDER_APP_PASSWORD at the top of smartgate_yolo.py.",
                )
                return
            msg.config(fg=MUTED, text="Sending…")
            top.update_idletasks()
            row = self.db.staff_get(ident) or self.db.staff_by_email(ident)
            if row and row["active"] and row["email"]:
                code = f"{secrets.randbelow(10**6):06d}"
                try:
                    send_reset_email(row["email"], code)
                except Exception as e:
                    msg.config(fg=RED, text=f"Could not send the email: {e}")
                    return
                state.update(
                    row=row,
                    hash=hashlib.sha256(code.encode()).hexdigest(),
                    expires=time.time() + RESET_CODE_MINUTES * 60,
                    tries=0,
                )
            # same message either way, so nobody can find out which accounts exist
            msg.config(
                fg="#047857",
                text="If this account has a saved "
                "email, a code has been sent. Check your inbox and spam.",
            )
            step2.pack(fill="x")
            f_code.focus()

        def reset():
            code = f_code.get()
            row = state["row"]
            state["tries"] += 1
            if (
                not row
                or time.time() > state["expires"]
                or state["tries"] > RESET_MAX_TRIES
                or not hmac.compare_digest(
                    hashlib.sha256(code.encode()).hexdigest(), state["hash"] or ""
                )
            ):
                f_code.error("Wrong or expired code. Send a new code and try again.")
                return
            ok = True
            for f, fn in ((f_pw, password_problem), (f_pw2, confirm_msg)):
                m = fn(f.get())
                if m:
                    f.error(m)
                    ok = False
                else:
                    f.good()
            if not ok:
                return
            self.db.set_password(row["username"], f_pw.get())
            state["row"] = None
            top.destroy()
            messagebox.showinfo(
                "Password updated",
                "Your password was changed. You can now log in.",
                parent=self,
            )

        Btn(cd, "Send code to my email", send).pack(fill="x", pady=(8, 4))
        Btn(step2, "Reset password", reset, "green").pack(fill="x", pady=(10, 4))
        f_id.focus()

    def change_email_dialog(self, row):
        """Save or change the recovery email of a staff account (full-access roles only)."""
        top = self.popup("Recovery email", f'Account: {row["full_name"]}', 430, 300)
        cd = card(top.content, padx=24, pady=12)
        cd.pack(fill="x", padx=22)
        field = FormField(cd, "Email", hint="e.g. name@gmail.com", wrap=350)
        field.pack(fill="x")
        field.entry.insert(0, row["email"] or "")

        def save():
            m = self.msg_staff_email(field.get(), current=row["username"])
            if m:
                field.error(m)
                return
            self.db.set_email(row["username"], field.get())
            top.destroy()
            self.navigate("staff")
            messagebox.showinfo("Saved", "Recovery email saved.", parent=self)

        Btn(cd, "Save email", save).pack(fill="x", pady=(10, 4))
        field.focus()

    def do_login(self):
        self.login_msg.config(text="")
        u, p = self.e_user.get().lower(), self.e_pass.entry.get()
        username_error = (
            "Username is required." if not u else username_problem(u)
        )
        password_error = "Password is required." if not p else ""
        if username_error:
            self.e_user.error(username_error)
        else:
            self.e_user.good()
        if password_error:
            self.e_pass.error(password_error)
        else:
            self.e_pass.good()
        if username_error or password_error:
            return
        row = self.db.check_password(u, p)
        if row and not row["active"]:
            self.login_msg.config(
                text="This account is disabled. Please contact an administrator."
            )
            return
        if row:
            self.start_session(row)
            return
        self.e_user.row.config(highlightbackground=RED, highlightcolor=RED)
        self.e_pass.row.config(highlightbackground=RED, highlightcolor=RED)
        self.login_msg.config(text="Incorrect username or password. Please try again.")

    # ------------------------------------------------------------------
    # SECTION 7: AUTHENTICATED APP SHELL, SIDEBAR, AND NAVIGATION
    # NAV keys must match the corresponding page_<key>() methods below.
    # ------------------------------------------------------------------
    FULL_ACCESS_NAV = [
        ("dashboard", "Dashboard", "▦", False),
        ("verify", "Face Verification", "☺", False),
        ("register", "Student Registration", "✚", True),
        ("records", "Access Records", "☰", False),
        ("reports", "System Reports", "▮", True),
        ("staff", "Staff Accounts", "⚙", True),
    ]
    GUARD_NAV = [
        ("dashboard", "Dashboard", "▦", False),
        ("verify", "Face Verification", "☺", False),
        ("reports", "System Reports", "▮", True),
    ]

    def navigation_for_role(self):
        if self.role in FULL_ACCESS_ROLES:
            return self.FULL_ACCESS_NAV
        if self.role == "Security Guards":
            return self.GUARD_NAV
        return []

    def can_access_page(self, page):
        """Check access against the current role's navigation."""
        return page in {item[0] for item in self.navigation_for_role()}

    def build_shell(self):
        self.clear()
        self.side = tk.Frame(self, bg=NAVY, width=230)
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)
        self.main = tk.Frame(self, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        # Centered copyright footer on every authenticated page.
        self.main_footer = tk.Label(
            self.main,
            text="© 2026 Samtse College of Education. All rights reserved.",
            bg=BG,
            fg=MUTED,
            font=F(8),
            anchor="center",
            pady=6,
        )
        self.main_footer.pack(side="bottom", fill="x")

        # Compact SCE Smart Gate brand mark shown consistently in the navigation
        # sidebar on every authenticated page. Uses the existing college_logo.png.
        logo = tk.Frame(self.side, bg=NAVY)
        logo.pack(anchor="w", padx=14, pady=(18, 20), fill="x")
        logo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "college_logo.png"
        )
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_img.thumbnail((34, 36), Image.Resampling.LANCZOS)
            self.sidebar_logo_photo = ImageTk.PhotoImage(logo_img)
            tk.Label(logo, image=self.sidebar_logo_photo, bg=NAVY, bd=0).pack(
                side="left", padx=(0, 8)
            )
        except Exception:
            tk.Label(
                logo,
                text="SCE",
                bg=PRIMARY,
                fg="white",
                font=F(9, "bold"),
                width=4,
                height=2,
            ).pack(side="left", padx=(0, 8))
        t = tk.Frame(logo, bg=NAVY)
        t.pack(side="left", padx=0, fill="x", expand=True)
        tk.Label(t, text="Smart Gate", bg=NAVY, fg="white", font=F(11, "bold")).pack(
            anchor="w"
        )
        tk.Label(
            t,
            text="Samtse College of Education",
            bg=NAVY,
            fg="#A9C0D3",
            font=F(7),
            wraplength=145,
            justify="left",
        ).pack(anchor="w")

        tk.Frame(self.side, bg=NAVY, height=35).pack()
        self.nav_items = {}
        for key, label, icon, admin_only in self.navigation_for_role():
            lb = tk.Label(
                self.side,
                text=f"  {icon}   {label}",
                bg=NAVY,
                fg="#C7D6E4",
                font=F(9),
                anchor="w",
                padx=10,
                pady=9,
                cursor="hand2",
            )
            lb.pack(fill="x", padx=12, pady=1)
            lb.bind("<Button-1>", lambda e, k=key: self.navigate(k))
            self.nav_items[key] = lb
            lb.bind(
                "<Enter>", lambda e, k=key: self.nav_items[k].config(bg=NAVY_ACTIVE)
            )
            lb.bind(
                "<Leave>",
                lambda e, k=key: self.nav_items[k].config(
                    bg=NAVY_ACTIVE if k == self.current_page else NAVY
                ),
            )

        bottom = tk.Frame(self.side, bg=NAVY)
        bottom.pack(side="bottom", fill="x", padx=16, pady=16)
        so = tk.Label(
            bottom,
            text="  ⇥  Log out",
            bg="#2A2F45",
            fg=RED,
            font=F(9, "bold"),
            anchor="w",
            pady=8,
            cursor="hand2",
        )
        so.pack(side="bottom", fill="x", pady=(10, 0))
        so.bind("<Button-1>", lambda e: self.do_logout())
        so.bind("<Enter>", lambda e: so.config(bg="#3A1F2E"))
        so.bind("<Leave>", lambda e: so.config(bg="#2A2F45"))
        credential_note = tk.Label(
            bottom,
            text="  Credentials managed by authorized staff",
            bg=NAVY,
            fg="#A9C0D3",
            font=F(7),
            anchor="w",
            pady=6,
            wraplength=190,
            justify="left",
        )
        credential_note.pack(side="bottom", fill="x")
        who = tk.Frame(
            bottom,
            bg="#163957",
            padx=10,
            pady=10,
            highlightthickness=1,
            highlightbackground="#294B6A",
        )
        who.pack(side="bottom", fill="x", pady=(0, 10))
        who.grid_columnconfigure(1, weight=1)
        av = tk.Canvas(who, width=38, height=38, bg="#163957", highlightthickness=0)
        av.create_oval(1, 1, 37, 37, fill="#C08A5B", outline="")
        av.create_text(
            19,
            19,
            text=self.me["full_name"][:1].upper(),
            fill="white",
            font=F(11, "bold"),
        )
        av.grid(row=0, column=0, rowspan=3, sticky="n", padx=(0, 10))
        t2 = tk.Frame(who, bg="#163957")
        t2.grid(row=0, column=1, sticky="ew")
        t2.grid_columnconfigure(0, weight=1)
        tk.Label(
            t2,
            text=self.me["full_name"],
            bg="#163957",
            fg="white",
            font=F(9, "bold"),
            wraplength=122,
            justify="left",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            t2,
            text=self.role,
            bg="#163957",
            fg="#C7D6E4",
            font=F(8),
            wraplength=122,
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(3, 0))
        tk.Label(
            t2,
            text="Signed in " + getattr(self, "login_time", now()).strftime("%I:%M %p"),
            bg="#163957",
            fg="#A9C0D3",
            font=F(8),
            wraplength=122,
            justify="left",
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", pady=(2, 0))

    def do_logout(self):
        if messagebox.askyesno(
            "Log out", "Are you sure you want to log out of Smart Gate?", parent=self
        ):
            self.show_welcome()

    def navigate(self, page):
        if not self.can_access_page(page):
            messagebox.showwarning(
                "Access restricted",
                "Your account does not have permission to open this page.",
                parent=self,
            )
            return
        self.stop_camera()  # camera is only on while a page needs it
        self.capturing = False
        self.current_page = page
        for k, lb in self.nav_items.items():
            lb.config(
                bg=NAVY_ACTIVE if k == page else NAVY,
                fg="white" if k == page else "#C7D6E4",
            )
        getattr(self, "page_" + page)()

    def page_frame(self, title, subtitle):
        self.clear(self.main)
        self.clock_lbl = None
        head = tk.Frame(self.main, bg=BG)
        head.pack(fill="x", padx=32, pady=(28, 16))
        t = tk.Frame(head, bg=BG)
        t.pack(side="left")
        tk.Label(t, text=title, bg=BG, fg=INK, font=F(18, "bold")).pack(anchor="w")
        tk.Label(t, text=subtitle, bg=BG, fg=MUTED, font=F(9)).pack(anchor="w")
        clk = card(head)
        clk.pack(side="right", anchor="n")
        self.clock_lbl = tk.Label(
            clk, text=now().strftime("%I:%M:%S %p"), bg=CARD, fg=INK, font=F(9, "bold")
        )
        self.clock_lbl.pack(side="left", padx=(10, 6), pady=6)
        tk.Label(clk, text="Samtse Standard Time", bg=CARD, fg=MUTED, font=F(7)).pack(
            side="left", padx=(0, 10)
        )
        viewport = tk.Frame(self.main, bg=BG)
        viewport.pack(fill="both", expand=True, padx=24, pady=(0, 10))
        canvas = tk.Canvas(viewport, bg=BG, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=BG)
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_body_width(event):
            canvas.itemconfigure(window_id, width=event.width)

        body.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", fit_body_width)
        canvas.bind(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )
        body.bind(
            "<Enter>",
            lambda e: canvas.bind_all(
                "<MouseWheel>",
                lambda ev: canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"),
            ),
        )
        body.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        self.page_canvas = canvas
        return body

    # ------------------------------------------------------------------
    # SECTION 7A: SHARED DIALOGS AND INTERACTIVE POP-UPS
    # ------------------------------------------------------------------
    def users_where(self, kind="all", utype=None):
        out = []
        for u in self.db.users():
            if utype and u["type"] != utype:
                continue
            if kind == "inside" and self.db.status(u["uid"]) != "Inside":
                continue
            out.append(u)
        return out

    def refresh_page(self):
        if self.current_page in ("dashboard", "records", "reports"):
            self.navigate(self.current_page)

    def popup(self, title, subtitle, w=640, h=480, big=False):
        """Pop-up window with a scrolling body. Put your widgets in `top.content`."""
        top = tk.Toplevel(self)
        top.title(title)
        top.configure(bg=BG)
        top.transient(self)
        # never taller or wider than the screen
        w = min(w, self.winfo_screenwidth() - 40)
        h = min(h, self.winfo_screenheight() - 100)
        x = max(self.winfo_rootx() + (self.winfo_width() - w) // 2, 0)
        y = max(self.winfo_rooty() + (self.winfo_height() - h) // 2, 30)
        top.geometry(f"{w}x{h}+{x}+{y}")
        top.bind("<Escape>", lambda e: top.destroy())
        head = tk.Frame(top, bg=BG)
        head.pack(fill="x", padx=22, pady=(18, 10))
        t = tk.Frame(head, bg=BG)
        t.pack(side="left")
        tk.Label(t, text=title, bg=BG, fg=INK, font=F(20 if big else 14, "bold")).pack(
            anchor="w"
        )
        tk.Label(t, text=subtitle, bg=BG, fg=MUTED, font=F(10 if big else 9)).pack(
            anchor="w"
        )
        x_ = tk.Label(head, text="✕", bg=BG, fg=MUTED, font=F(12), cursor="hand2")
        x_.pack(side="right", anchor="n")
        x_.bind("<Button-1>", lambda e: top.destroy())

        body = tk.Frame(top, bg=BG)
        body.pack(fill="both", expand=True)
        canvas = tk.Canvas(body, bg=BG, highlightthickness=0, borderwidth=0)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scrollbar.set)
        content = tk.Frame(canvas, bg=BG)
        content_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def update_scroll_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def fit_width(event):
            canvas.itemconfigure(content_id, width=event.width)

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", fit_width)
        canvas.bind(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )
        top.bind(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )
        top.content = content
        top.canvas = canvas

        top.focus_set()
        return top

    def make_tree(self, parent, cols):
        wrap = card(parent)
        wrap.pack(fill="both", expand=True, padx=22, pady=(0, 16))
        tree = ttk.Treeview(
            wrap, columns=[c[0] for c in cols], show="headings", selectmode="browse"
        )
        for key, title, w in cols:
            tree.heading(key, text=title, anchor="w")
            tree.column(key, width=w, anchor="w")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)
        tree.tag_configure("in", foreground="#047857")
        tree.tag_configure("out", foreground=MUTED)
        return tree

    def tree_open(self, tree, event=None, uids=None):
        if event is not None and tree.identify_region(event.x, event.y) != "cell":
            return
        sel = tree.selection()
        if sel:
            self.user_detail(uids[sel[0]] if uids else sel[0])

    def users_dialog(self, title, users):
        top = self.popup(
            title, f"{len(users)} user(s) · double-click a row for the full profile"
        )
        q = tk.StringVar()
        sw = card(top.content)
        sw.pack(fill="x", padx=22, pady=(0, 10))
        tk.Label(sw, text="🔍", bg=CARD, fg=MUTED).pack(side="left", padx=(10, 0))
        tk.Entry(
            sw,
            textvariable=q,
            relief="flat",
            bg=CARD,
            fg=INK,
            font=F(9),
            insertbackground=INK,
        ).pack(side="left", fill="x", expand=True, ipady=7, padx=6)
        tree = self.make_tree(
            top.content,
            [
                ("name", "NAME", 170),
                ("uid", "ID", 90),
                ("type", "TYPE", 80),
                ("prog", "PROGRAMME", 85),
                ("course", "COURSE / DEPT", 110),
                ("status", "STATUS", 70),
            ],
        )

        def fill(*_):
            tree.delete(*tree.get_children())
            term = q.get().strip().lower()
            for u in users:
                if (
                    term
                    and term
                    not in (
                        f'{u["name"]} {u["uid"]} {u["programme"]} '
                        f'{u["course"] or ""} {u["email"] or ""}'
                    ).lower()
                ):
                    continue
                st = self.db.status(u["uid"])
                tree.insert(
                    "",
                    "end",
                    iid=u["uid"],
                    tags=("in" if st == "Inside" else "out",),
                    values=(
                        u["name"],
                        u["uid"],
                        u["type"],
                        u["programme"],
                        u["course"] or "",
                        st,
                    ),
                )

        q.trace_add("write", fill)
        fill()
        tree.bind("<Double-1>", lambda e: self.tree_open(tree, e))
        tree.bind("<Return>", lambda e: self.tree_open(tree))

    def logs_dialog(self, title, logs):
        top = self.popup(
            title, f"{len(logs)} event(s) · double-click a row for the full profile"
        )
        tree = self.make_tree(
            top.content,
            [
                ("name", "NAME / ID", 230),
                ("type", "TYPE", 90),
                ("action", "ACTION", 90),
                ("date", "DATE", 100),
                ("time", "TIME", 90),
            ],
        )
        uids = {}
        for l in logs:
            dt = datetime.strptime(l["ts"], "%Y-%m-%d %H:%M:%S")
            iid = str(l["id"])
            uids[iid] = l["uid"]
            entry = l["action"] == "Entry"
            tree.insert(
                "",
                "end",
                iid=iid,
                tags=("in" if entry else "out",),
                values=(
                    f'{l["name"]}  ({l["uid"]})',
                    l["type"],
                    ("↓ " if entry else "↑ ") + l["action"],
                    dt.strftime("%d/%m/%Y"),
                    dt.strftime("%I:%M %p"),
                ),
            )
        tree.bind("<Double-1>", lambda e: self.tree_open(tree, e, uids))
        tree.bind("<Return>", lambda e: self.tree_open(tree, None, uids))

    def user_detail(self, uid):
        u = self.db.user(uid)
        if not u:
            return
        top = self.popup(
            u["name"], f'{u["type"]}  ·  {u["programme"]}', 700, 720, big=True
        )
        st = self.db.status(uid)
        inside = st == "Inside"
        hist = self.db.user_logs(uid)
        initials = "".join(w[0] for w in u["name"].split()[:2]).upper() or "?"

        cd = card(top.content, padx=22, pady=18)
        cd.pack(fill="x", padx=22, pady=(0, 12))
        av = tk.Canvas(cd, width=72, height=72, bg=CARD, highlightthickness=0)
        av.create_oval(2, 2, 70, 70, fill="#DBEAFE", outline="")
        av.create_text(36, 36, text=initials, fill=PRIMARY, font=F(20, "bold"))
        av.pack(side="left", anchor="n")
        tk.Label(
            cd,
            text=("●  " + st),
            bg=GREEN_L if inside else FIELD,
            fg="#047857" if inside else MUTED,
            font=F(9, "bold"),
            padx=12,
            pady=4,
        ).pack(side="right", anchor="n")
        grid_ = tk.Frame(cd, bg=CARD)
        grid_.pack(side="left", padx=(18, 0), fill="x", expand=True)
        for r_, (lab, val) in enumerate(
            [
                ("ID", u["uid"]),
                ("Email", u["email"] or "—"),
                ("Course / Department", u["course"] or "—"),
                ("Face data", f'{u["faces"]} images enrolled'),
            ]
        ):
            tk.Label(
                grid_,
                text=lab.upper(),
                bg=CARD,
                fg=MUTED,
                font=F(7, "bold"),
                anchor="w",
                width=20,
            ).grid(row=r_, column=0, sticky="w", pady=3)
            tk.Label(
                grid_, text=val, bg=CARD, fg=INK, font=F(10, "bold"), anchor="w"
            ).grid(row=r_, column=1, sticky="w", pady=3)

        entries = sum(1 for l in hist if l["action"] == "Entry")
        last = "—"
        if hist:
            last = datetime.strptime(hist[0]["ts"], "%Y-%m-%d %H:%M:%S").strftime(
                "%d/%m %I:%M %p"
            )
        sr = tk.Frame(top.content, bg=BG)
        sr.pack(fill="x", padx=18, pady=(0, 10))
        for i, (lab, val) in enumerate(
            [
                ("Total entries", entries),
                ("Total exits", len(hist) - entries),
                ("Last activity", last),
            ]
        ):
            sr.columnconfigure(i, weight=1, uniform="d")
            k = card(sr, padx=12, pady=8)
            k.grid(row=0, column=i, sticky="ew", padx=4)
            tk.Label(k, text=lab, bg=CARD, fg=MUTED, font=F(8)).pack(anchor="w")
            tk.Label(k, text=str(val), bg=CARD, fg=INK, font=F(12, "bold")).pack(
                anchor="w"
            )

        # action buttons sit above the history table so they are always visible
        bar = tk.Frame(top.content, bg=BG)
        bar.pack(fill="x", padx=22, pady=(0, 16))
        if self.role in FULL_ACCESS_ROLES:
            nxt = "Exit" if inside else "Entry"

            def manual():
                self.db.record_gate_event(uid)
                top.destroy()
                self.refresh_page()
                self.user_detail(uid)

            def delete():
                if messagebox.askyesno(
                    "Delete user",
                    f'Delete {u["name"]}, their face data and all logs?\n'
                    "This cannot be undone.",
                    parent=top,
                ):
                    self.db.delete_user(uid)
                    self.engine.remove(uid)
                    if self.verified and self.verified["uid"] == uid:
                        self.verified = None
                    top.destroy()
                    self.refresh_page()

            Btn(
                bar,
                "Record next gate action (manual override)",
                manual,
                "green" if nxt == "Entry" else "primary",
                padx=14,
            ).pack(side="left")
            Btn(bar, "Delete User", delete, "red", padx=14).pack(side="left", padx=8)
        else:
            tk.Label(
                bar,
                text="Manual overrides and deletion are available to authorized staff only.",
                bg=BG,
                fg=MUTED,
                font=F(8),
            ).pack(anchor="w")
        tk.Label(
            top.content, text="GATE HISTORY", bg=BG, fg=MUTED, font=F(8, "bold")
        ).pack(anchor="w", padx=22, pady=(0, 4))
        tree = self.make_tree(
            top.content,
            [("date", "DATE", 160), ("time", "TIME", 160), ("action", "ACTION", 160)],
        )
        for l in hist:
            dt = datetime.strptime(l["ts"], "%Y-%m-%d %H:%M:%S")
            entry = l["action"] == "Entry"
            tree.insert(
                "",
                "end",
                tags=("in" if entry else "out",),
                values=(
                    dt.strftime("%d/%m/%Y"),
                    dt.strftime("%I:%M %p"),
                    ("↓ " if entry else "↑ ") + l["action"],
                ),
            )

    # ==================================================================
    # SECTION 9: FACE VERIFICATION PAGE
    # Main page method: page_verify(); helpers: verify_*()
    # ==================================================================
    def page_verify(self):
        self.verified = None
        body = self.page_frame(
            "Face Verification", "Look at the camera to verify your identity"
        )
        self.vbody = body
        self.verify_start()

    def verify_card(self):
        self.clear(self.vbody)
        wrap = tk.Frame(self.vbody, bg=BG)
        wrap.pack(pady=6)
        cd = card(wrap, padx=30, pady=22)
        cd.pack()
        return wrap, cd

    def verify_notice(self, title, text, btn_text, btn_cmd):
        wrap, cd = self.verify_card()
        cd.config(padx=50, pady=30)
        cross_circle(cd).pack()
        tk.Label(cd, text=title, bg=CARD, fg=RED, font=F(13, "bold")).pack(pady=(14, 2))
        tk.Label(
            cd,
            text=text,
            bg=CARD,
            fg=MUTED,
            font=F(9),
            wraplength=380,
            justify="center",
        ).pack()
        Btn(cd, btn_text, btn_cmd).pack(fill="x", pady=(20, 0), ipadx=60)

    def verify_start(self):
        self.stop_camera()
        if not self.engine.rec:
            if self.role in FULL_ACCESS_ROLES:
                self.verify_notice(
                    "No registered faces yet",
                    "Register at least one user with a face capture first.",
                    "Go to Student Registration",
                    lambda: self.navigate("register"),
                )
            else:
                self.verify_notice(
                    "No registered faces yet",
                    "Ask System Administrator or College Management to register users first.",
                    "Back to Dashboard",
                    lambda: self.navigate("dashboard"),
                )
            return
        if not self.start_camera():
            self.verify_notice(
                "Camera not available",
                "Could not open the webcam. Close other apps using it "
                "and check the camera is connected.",
                "Try Again",
                self.verify_start,
            )
            return

        wrap, cd = self.verify_card()
        frame_box = tk.Frame(cd, width=VIEW_SIZE[0], height=VIEW_SIZE[1], bg="#0F172A")
        frame_box.pack()
        frame_box.pack_propagate(False)
        video = tk.Label(
            frame_box, text="Starting camera…", bg="#0F172A", fg="white", font=F(10)
        )
        video.pack(fill="both", expand=True)
        status = tk.Label(
            cd,
            text="Look straight at the camera",
            bg=CARD,
            fg=PRIMARY,
            font=F(11, "bold"),
        )
        status.pack(pady=(14, 2))
        tk.Label(
            cd,
            text="Only registered people are recognised. Unregistered faces are "
            "shown as “Unknown”.",
            bg=CARD,
            fg=MUTED,
            font=F(8),
        ).pack()
        tk.Label(
            wrap,
            text="●  Live camera is active. Hold still for a moment while the "
            "system confirms your identity.",
            bg=BG,
            fg=MUTED,
            font=F(8),
        ).pack(pady=12)

        state = {"uid": None, "n": 0, "sims": []}

        def loop():
            if not video.winfo_exists() or self.cam is None:
                return
            frame = self.cam.read()
            if frame is not None:
                gray, boxes = self.engine.detect(frame)
                results = []
                for box in boxes:
                    uid, dist = self.engine.predict(self.engine.crop(gray, box))
                    results.append((box, uid, 1 - dist))
                main_uid, main_sim = None, 0.0
                if results:
                    # the largest (closest) face is the one being verified
                    main_box, main_uid, main_sim = max(
                        results, key=lambda r: r[0][2] * r[0][3]
                    )
                for box, uid, sim in results:
                    shown = f" {sim:.2f}" if DEBUG_SCORES else ""
                    if uid:
                        name = self.db.user(uid)["name"] if self.db.user(uid) else ""
                        label = name.encode("ascii", "ignore").decode() or "Registered"
                        self.draw_box(frame, box, (129, 185, 16), label + shown)
                    else:
                        self.draw_box(frame, box, (68, 68, 239), "Unknown" + shown)
                if main_uid and main_uid == state["uid"]:
                    state["n"] += 1
                    state["sims"].append(main_sim)
                else:
                    state["uid"], state["n"] = main_uid, (1 if main_uid else 0)
                    state["sims"] = [main_sim] if main_uid else []
                self.show_frame(video, frame, VIEW_SIZE)
                if state["n"] >= CONFIRM_FRAMES:
                    recent = state["sims"][-CONFIRM_FRAMES:]
                    if sum(recent) / len(recent) >= MATCH_SIM + CONFIRM_AVG_BONUS:
                        self.verify_found(state["uid"])
                        return
                if not results:
                    status.config(
                        text="No face detected — look at the camera", fg=MUTED
                    )
                elif main_uid is None:
                    status.config(text="Face not registered", fg=RED)
                else:
                    status.config(text="Verifying…", fg=PRIMARY)
            self.later(50, loop)

        loop()

    def verify_found(self, uid):
        self.stop_camera()
        user = self.db.user(uid)
        if user is None:  # stale template for a deleted user
            self.verify_start()
            return
        self.verified = user
        self.page_entry_exit()

    # ==================================================================
    # SECTION 10: ENTRY / EXIT RECORDING WORKFLOW
    # ==================================================================
    def page_entry_exit(self):
        if not self.verified:
            return self.navigate("verify")
        u = self.verified
        action, timestamp = self.db.record_gate_event(u["uid"])
        self.verified = None
        when = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        body = self.page_frame(f"{action} Recorded", "Gate activity has been logged")
        cd = card(body, padx=40, pady=30, border="#A7F3D0")
        cd.pack(pady=10, ipadx=80)
        check_circle(cd).pack()
        tk.Label(
            cd,
            text=f"{action} recorded successfully",
            bg=CARD,
            fg=INK,
            font=F(13, "bold"),
        ).pack(pady=(14, 2))
        tk.Label(
            cd,
            text=f'{u["name"]} ({u["uid"]})',
            bg=CARD,
            fg=PRIMARY,
            font=F(10, "bold"),
        ).pack()
        tk.Label(
            cd, text=when.strftime("%I:%M %p · %d/%m/%Y"), bg=CARD, fg=MUTED, font=F(9)
        ).pack(pady=(4, 0))
        direction = (
            "may enter the college" if action == "Entry" else "has left the college"
        )
        tk.Label(cd, text=direction, bg=CARD, fg=INK, font=F(9)).pack(pady=(8, 0))

        def scan_next():
            self.navigate("verify")

        Btn(cd, "Scan Next Person", scan_next, "outline").pack(fill="x", pady=(16, 0))

    # one checker per field: each returns an error message, or "" when the text is fine

    # ==================================================================
    # SECTION 12: ACCESS RECORDS PAGE, SEARCH, FILTER, AND CSV EXPORT
    # Main page method: page_records()
    # ==================================================================
    def page_records(self):
        body = self.page_frame(
            "Entry / Exit Records", "Search and review gate activity logs"
        )
        self.rec_filter = getattr(self, "rec_filter", "All")
        self.sort = ("ts", True)
        bar = tk.Frame(body, bg=BG)
        bar.pack(fill="x", pady=(0, 10))
        sw = card(bar)
        sw.pack(side="left", fill="x", expand=True, padx=(0, 10))
        tk.Label(sw, text="🔍", bg=CARD, fg=MUTED).pack(side="left", padx=(10, 0))
        self.search = tk.StringVar()
        tk.Entry(
            sw,
            textvariable=self.search,
            relief="flat",
            bg=CARD,
            fg=INK,
            font=F(9),
            insertbackground=INK,
        ).pack(side="left", fill="x", expand=True, ipady=8, padx=6)
        self.search.trace_add("write", lambda *a: self.fill_records())
        self.fbtn = {}
        for f in ("All", "Inside", "Outside"):
            b = tk.Label(
                bar,
                text=f,
                font=F(9),
                padx=14,
                pady=7,
                cursor="hand2",
                highlightthickness=1,
            )
            b.pack(side="left", padx=3)
            b.bind("<Button-1>", lambda e, x=f: self.set_filter(x))
            self.fbtn[f] = b
        if self.role in FULL_ACCESS_ROLES:
            Btn(bar, "⭳ Export CSV", self.export_csv, "outline", padx=10).pack(
                side="left", padx=(8, 0)
            )

        cols = ("name", "type", "date", "time", "status")
        wrap = card(body)
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            wrap, columns=cols, show="headings", selectmode="browse"
        )
        for c, t, w in zip(
            cols,
            ("NAME / ID", "TYPE", "DATE", "ENTRY - EXIT", "STATUS"),
            (280, 120, 130, 130, 110),
        ):
            self.tree.heading(
                c, text=t, anchor="w", command=lambda k=c: self.sort_by(k)
            )
            self.tree.column(c, width=w, anchor="w")
        self.tree.tag_configure("in", foreground="#047857")
        self.tree.tag_configure("out", foreground=MUTED)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.tree_open(self.tree, e))
        self.tree.bind("<Return>", lambda e: self.tree_open(self.tree))
        tk.Label(
            body,
            text="Tip: click a column header to sort · double-click a row to open the profile.",
            bg=BG,
            fg=MUTED,
            font=F(8),
        ).pack(side="bottom", anchor="w", pady=(6, 0))
        self.set_filter(self.rec_filter)

    def sorted_rows(self):
        key, rev = self.sort
        keyf = {
            "name": lambda r: r["name"].lower(),
            "type": lambda r: r["type"],
            "date": lambda r: r["ts"][:10],
            "time": lambda r: r["ts"],
            "status": lambda r: r["action"],
            "ts": lambda r: r["ts"],
        }[key]
        return sorted(self.db.latest_rows(), key=keyf, reverse=rev)

    def sort_by(self, col):
        key, rev = self.sort
        self.sort = (col, (not rev) if key == col else False)
        self.fill_records()

    def export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            initialfile="smartgate_records.csv",
            filetypes=[("CSV file", "*.csv")],
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "Name",
                    "ID",
                    "Email",
                    "Type",
                    "Programme",
                    "Course / Department",
                    "Action",
                    "Date",
                    "Time",
                ]
            )
            for l in reversed(self.db.logs_full(today=False)):
                dt = datetime.strptime(l["ts"], "%Y-%m-%d %H:%M:%S")
                w.writerow(
                    [
                        l["name"],
                        l["uid"],
                        l["email"] or "",
                        l["type"],
                        l["programme"],
                        l["course"] or "",
                        l["action"],
                        dt.strftime("%d/%m/%Y"),
                        dt.strftime("%I:%M %p"),
                    ]
                )
        messagebox.showinfo("Export complete", f"Saved to:\n{path}")

    def set_filter(self, f):
        self.rec_filter = f
        for k, b in self.fbtn.items():
            on = k == f
            b.config(
                bg=GREEN_L if on else CARD,
                fg="#047857" if on else INK,
                highlightbackground=GREEN if on else BORDER,
            )
        self.fill_records()

    def fill_records(self):
        self.tree.delete(*self.tree.get_children())
        q = self.search.get().strip().lower()
        for r in self.sorted_rows():
            status = "Inside" if r["action"] == "Entry" else "Outside"
            if self.rec_filter != "All" and status != self.rec_filter:
                continue
            dt = datetime.strptime(r["ts"], "%Y-%m-%d %H:%M:%S")
            date = dt.strftime("%d/%m/%Y")
            if q and q not in f'{r["name"]} {r["uid"]} {date}'.lower():
                continue
            arrow = "↓" if r["action"] == "Entry" else "↑"
            self.tree.insert(
                "",
                "end",
                iid=r["uid"],
                tags=("in" if status == "Inside" else "out",),
                values=(
                    f'{r["name"]}   ({r["uid"]})',
                    r["type"],
                    date,
                    f'{arrow} {dt.strftime("%I:%M %p")}',
                    status,
                ),
            )

    # ==================================================================
    # SECTION 14: SYSTEM REPORTS AND ACTIVITY SUMMARIES
    # Main page method: page_reports()
    # ==================================================================

    def page_reports(self):
        body = self.page_frame(
            "Reports", "Summary of gate activity and campus statistics"
        )
        c = self.db.counts()
        logs = self.db.today_logs()
        entries = [l for l in logs if l["action"] == "Entry"]
        exits = [l for l in logs if l["action"] == "Exit"]

        row = tk.Frame(body, bg=BG)
        row.pack(fill="x")
        for i, (lab, val, dot) in enumerate(
            [
                ("Today's Entries", len(entries), None),
                ("Currently Inside", c["inside"], GREEN),
                ("Exits Today", len(exits), None),
            ]
        ):
            row.columnconfigure(i, weight=1, uniform="k")
            k = card(row, padx=16, pady=12)
            k.grid(row=0, column=i, sticky="ew", padx=6)
            tk.Label(k, text=lab, bg=CARD, fg=MUTED, font=F(9)).pack(anchor="w")
            tk.Label(
                k,
                text=(("● " if dot else "") + str(val)),
                bg=CARD,
                fg=INK,
                font=F(20, "bold"),
            ).pack(anchor="w")
            clickable(
                k,
                [
                    lambda: self.logs_dialog(
                        "Today's Entries", self.db.logs_full(action="Entry")
                    ),
                    lambda: self.users_dialog(
                        "Currently Inside", self.users_where("inside")
                    ),
                    lambda: self.logs_dialog(
                        "Exits Today", self.db.logs_full(action="Exit")
                    ),
                ][i],
            )

        row2 = tk.Frame(body, bg=BG)
        row2.pack(fill="both", expand=True, pady=12)
        for i in range(3):
            row2.columnconfigure(i, weight=1, uniform="c")

        def panel(col, title):
            p = card(row2, padx=16, pady=14)
            p.grid(row=0, column=col, sticky="new", padx=6)
            tk.Label(p, text=title, bg=CARD, fg=INK, font=F(8, "bold")).pack(
                anchor="w", pady=(0, 8)
            )
            return p

        def bar(parent, label, val, mx, color, right=None, cmd=None):
            r = tk.Frame(parent, bg=CARD)
            r.pack(fill="x", pady=4)
            top = tk.Frame(r, bg=CARD)
            top.pack(fill="x")
            tk.Label(top, text=label, bg=CARD, fg=MUTED, font=F(8)).pack(side="left")
            tk.Label(
                top,
                text=right if right is not None else str(val),
                bg=CARD,
                fg=INK,
                font=F(8, "bold"),
            ).pack(side="right")
            cv = tk.Canvas(r, height=8, bg=FIELD, highlightthickness=0)
            cv.pack(fill="x", pady=2)
            cv.bind(
                "<Configure>",
                lambda e, cv=cv, v=val, m=mx, col=color: (
                    cv.delete("all"),
                    cv.create_rectangle(
                        0, 0, e.width * (v / m if m else 0), 8, fill=col, outline=""
                    ),
                ),
            )
            if cmd:
                clickable(r, cmd)

        p1 = panel(0, "REGISTERED USERS BY TYPE")
        mx = max(c["total"], 1)
        bar(
            p1,
            "Student",
            c["reg_students"],
            mx,
            PRIMARY,
            cmd=lambda: self.users_dialog(
                "Registered Students", self.users_where("all", "Student")
            ),
        )
        bar(
            p1,
            "Lecturer",
            c["reg_lecturers"],
            mx,
            "#8B5CF6",
            cmd=lambda: self.users_dialog(
                "Registered Lecturers", self.users_where("all", "Lecturer")
            ),
        )
        if c["reg_guests"]:
            bar(
                p1,
                "Guest",
                c["reg_guests"],
                mx,
                "#F59E0B",
                cmd=lambda: self.users_dialog(
                    "Registered Guests", self.users_where("all", "Guest")
                ),
            )

        p2 = panel(1, "CURRENTLY INSIDE BY TYPE")
        bar(
            p2,
            "Student",
            c["students"],
            max(c["reg_students"], 1),
            GREEN,
            f'{c["students"]} / {c["reg_students"]}',
            cmd=lambda: self.users_dialog(
                "Students Inside", self.users_where("inside", "Student")
            ),
        )
        bar(
            p2,
            "Lecturer",
            c["lecturers"],
            max(c["reg_lecturers"], 1),
            GREEN,
            f'{c["lecturers"]} / {c["reg_lecturers"]}',
            cmd=lambda: self.users_dialog(
                "Lecturers Inside", self.users_where("inside", "Lecturer")
            ),
        )
        if c["reg_guests"]:
            bar(
                p2,
                "Guest",
                c["in_guests"],
                c["reg_guests"],
                GREEN,
                f'{c["in_guests"]} / {c["reg_guests"]}',
                cmd=lambda: self.users_dialog(
                    "Guests Inside", self.users_where("inside", "Guest")
                ),
            )

        p3 = panel(2, "ENTRY ACTIVITY TODAY")
        slots = [
            (6, "06:00 AM"),
            (8, "08:00 AM"),
            (10, "10:00 AM"),
            (12, "12:00 PM"),
            (14, "02:00 PM"),
            (16, "04:00 PM"),
            (18, "06:00 PM"),
        ]
        buckets = {h: 0 for h, _ in slots}
        for l in entries:
            h = int(l["ts"][11:13])
            key = max([s for s, _ in slots if s <= h], default=None)
            if key is not None:
                buckets[key] += 1
        peak = max(max(buckets.values()), 1)

        def slot_rows(h):
            def bucket(hr):
                return max([s for s, _ in slots if s <= hr], default=None)

            return [
                l
                for l in self.db.logs_full(action="Entry")
                if bucket(int(l["ts"][11:13])) == h
            ]

        for h, lab in slots:
            bar(
                p3,
                lab,
                buckets[h],
                peak,
                PRIMARY,
                cmd=lambda h=h, lab=lab: self.logs_dialog(
                    f"Entries from {lab}", slot_rows(h)
                ),
            )
        tk.Label(
            p3,
            text="Click any bar or card to drill down.",
            bg=CARD,
            fg=MUTED,
            font=F(7),
        ).pack(anchor="w", pady=(6, 0))


def reset_admin_cli():
    """
    Recover a full-access account without needing to remember its username.
    Run: python smartgate_yolo.py --reset-admin

    This changes only the selected staff account's password and active status.
    Registered people, face images, and access logs are preserved.
    """
    import getpass

    db = DB()
    try:
        admins = [r for r in db.staff_list() if r["role"] in FULL_ACCESS_ROLES]

        if not admins:
            print("No full-access accounts were found.")
            print(
                "No data was changed. Check that smartgate_yolo.db is in this folder."
            )
            return

        print("\nSMART GATE - FULL-ACCESS ACCOUNT RECOVERY")
        print("Choose the account whose password you want to reset:")
        print("-" * 72)
        for i, row in enumerate(admins, start=1):
            status = "Active" if row["active"] else "Disabled"
            print(
                f'{i}. {row["full_name"]} | Username: {row["username"]} | '
                f'Role: {row["role"]} | {status}'
            )
        print("-" * 72)

        while True:
            choice = input(
                f"Enter the number of the account to reset (1-{len(admins)}) "
                "or Q to cancel: "
            ).strip()
            if choice.lower() == "q":
                print("Cancelled. No data was changed.")
                return
            if choice.isdigit() and 1 <= int(choice) <= len(admins):
                row = admins[int(choice) - 1]
                break
            print("Please enter a valid number from the list, or Q to cancel.")

        while True:
            pw = getpass.getpass("Enter a new password: ")
            problem = password_problem(pw)
            if problem:
                print(" ", problem)
                continue
            if pw != getpass.getpass("Confirm the new password: "):
                print("The passwords do not match. Please try again.")
                continue
            break

        db.set_password(row["username"], pw)
        db.set_active(row["username"], True)
        print("\nPassword reset successfully.")
        print(f'Name: {row["full_name"]}')
        print(f'Username: {row["username"]}')
        print(f'Role: {row["role"]}')
        print("You can now log in using this username and the new password.")
        print("Registered people, face images, and access logs were not deleted.")
    finally:
        db.c.close()


def reset_data_cli():
    """Clear registered people, staff accounts, and access history without renaming files."""
    print("SMARTGATE FRESH START")
    print(
        "This will permanently delete all staff accounts, registered people, and access logs."
    )
    print(f"The existing database file will keep its name: {DB_PATH}")
    print(f"The face folder will keep its name: {FACE_DIR}")
    confirm = input("Type RESET to continue: ").strip()
    if confirm != "RESET":
        print("Cancelled. No data was changed.")
        return

    db = DB()
    try:
        db.c.execute("DELETE FROM logs")
        db.c.execute("DELETE FROM users")
        db.c.execute("DELETE FROM staff")
        db.c.execute("DELETE FROM sqlite_sequence WHERE name='logs'")
        db.c.commit()
    finally:
        db.c.close()

    # Remove registered face images but keep the faces_yolo folder itself.
    os.makedirs(FACE_DIR, exist_ok=True)
    for name in os.listdir(FACE_DIR):
        path = os.path.join(FACE_DIR, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        elif os.path.isfile(path) or os.path.islink(path):
            os.remove(path)

    print("Fresh start complete. File and folder names were not changed.")
    print("Now start the app normally: python smartgate_yolo.py")
    print(
        "The first-time setup screen should ask you to create a new System Administrator."
    )


if __name__ == "__main__":
    if "--reset-admin" in sys.argv:
        reset_admin_cli()
    elif "--reset-data" in sys.argv:
        reset_data_cli()
    elif not DEPS_OK:
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("Setup needed", PROBLEM + "\n\nThen start the app again.")
    else:
        App().mainloop()
