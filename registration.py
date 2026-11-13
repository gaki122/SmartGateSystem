# Student, lecturer, and guest registration page mixin

import re
import time
import tkinter as tk
from tkinter import ttk

from smartgate_yolo import (
    BORDER,
    BURST,
    Btn,
    CARD,
    ComboField,
    F,
    FormField,
    GREEN,
    INK,
    MUTED,
    PRIMARY,
    PROGRAMMES_BY_TYPE,
    RED,
    SAMPLES_NEEDED,
    SHOTS,
    SHOT_PROMPTS,
    card,
    check_circle,
)


class RegistrationMixin:

    def page_register(self):
        body = self.page_frame(
            "Student Registration",
            "Add a new student, lecturer or guest with live face enrollment",
        )
        self.samples, self.burst, self.shots_done, self.retakes = [], [], 0, 0
        self.capturing, self.last_cap = False, 0.0
        body.columnconfigure((0, 1), weight=1, uniform="r")
        left = card(body, padx=20, pady=16)
        left.grid(row=0, column=0, sticky="new", padx=(0, 8))
        tk.Label(
            left, text="PERSONAL INFORMATION", bg=CARD, fg=MUTED, font=F(8, "bold")
        ).pack(anchor="w")
        row1 = tk.Frame(left, bg=CARD)
        row1.pack(fill="x")
        row1.columnconfigure((0, 1), weight=1, uniform="f1")
        self.r_name = FormField(row1, "Full Name", wrap=230)
        self.r_name.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.r_id = FormField(row1, "Student / Staff ID", wrap=230)
        self.r_id.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.r_email = FormField(left, "Email ID", hint="e.g. name@gmail.com")
        self.r_email.pack(fill="x")
        row3 = tk.Frame(left, bg=CARD)
        row3.pack(fill="x")
        row3.columnconfigure((0, 1), weight=1, uniform="f3")
        self.r_type = ComboField(row3, "User Type", ["Student", "Lecturer", "Guest"])
        self.r_type.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.r_type.set("")
        self.r_prog = ComboField(row3, "Programme", [])
        self.r_prog.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self.r_type.box.bind(
            "<<ComboboxSelected>>", lambda e: self.on_type_change(), add="+"
        )
        self.r_course = FormField(
            left, "Course / Department", hint="type it, e.g. ICT, English"
        )
        self.r_course.pack(fill="x")
        clr = tk.Label(
            left,
            text="Clear form",
            bg=CARD,
            fg=MUTED,
            font=F(8, "underline"),
            cursor="hand2",
        )
        clr.pack(anchor="w", pady=(14, 0))
        clr.bind("<Button-1>", lambda e: self.clear_register_form())
        self.setup_live_validation()

        right = card(body, padx=20, pady=16)
        right.grid(row=0, column=1, sticky="new", padx=(8, 0))
        tk.Label(
            right, text="FACE ENROLLMENT", bg=CARD, fg=PRIMARY, font=F(8, "bold")
        ).pack(anchor="w")
        fb = tk.Frame(right, width=320, height=240, bg="#0F172A")
        fb.pack(pady=(10, 8))
        fb.pack_propagate(False)
        self.reg_video = tk.Label(
            fb, text="Starting camera…", bg="#0F172A", fg="white", font=F(9)
        )
        self.reg_video.pack(fill="both", expand=True)
        self.fp_text = tk.Label(
            right, text=SHOT_PROMPTS[0], bg=CARD, fg=MUTED, font=F(9)
        )
        self.fp_text.pack()
        self.progress = ttk.Progressbar(right, maximum=SHOTS, mode="determinate")
        self.progress.pack(fill="x", pady=(8, 0))
        self.fp_btn = Btn(right, "Take Photo", self.toggle_capture, "outline")
        self.retake_lbl = tk.Label(
            right, text="", bg=CARD, fg=PRIMARY, font=F(8, "underline"), cursor="hand2"
        )
        self.retake_lbl.bind("<Button-1>", lambda e: self.retake())
        self.fp_btn.pack(fill="x", pady=(12, 6))
        self.retake_lbl.pack(anchor="w")
        tk.Label(
            right,
            text="Tip: good light, one person in frame. While the photo is taken (about 2 seconds), "
            "keep your face in view and turn your head very slightly left and right.",
            bg=CARD,
            fg=MUTED,
            font=F(7),
            wraplength=320,
            justify="left",
        ).pack(anchor="w")
        self.reg_msg = tk.Label(
            right, text="", bg=CARD, fg=RED, font=F(8), wraplength=320, justify="left"
        )
        self.reg_msg.pack(anchor="w", pady=(6, 0))
        tk.Frame(right, bg=BORDER, height=1).pack(fill="x", pady=8)
        Btn(right, "Register User", self.do_register).pack(fill="x")
        tk.Label(
            right, text="Fields marked * are required.", bg=CARD, fg=MUTED, font=F(7)
        ).pack(anchor="w", pady=(8, 0))

        if self.start_camera():
            self.reg_loop()
        else:
            self.reg_video.config(
                text="Camera not available.\nCheck the webcam, then press "
                "“Take Photo” to retry."
            )

    def reg_loop(self):
        if not self.reg_video.winfo_exists() or self.cam is None:
            return
        frame = self.cam.read()
        if frame is not None:
            gray, boxes = self.engine.detect(frame)
            if len(boxes) == 1:
                self.draw_box(frame, boxes[0], (129, 185, 16), "")
                if self.capturing and time.time() - self.last_cap >= 0.14:
                    self.last_cap = time.time()
                    self.burst.append(self.engine.crop(gray, boxes[0]))
                    if len(self.burst) >= BURST:
                        self.finish_shot()
            else:
                for b in boxes:
                    self.draw_box(frame, b, (68, 68, 239), "")
                if self.capturing:
                    self.fp_text.config(
                        text=(
                            "Only one face must be in view"
                            if boxes
                            else "No face detected"
                        ),
                        fg=RED,
                    )
            self.show_frame(self.reg_video, frame, (320, 240))
        self.later(40, self.reg_loop)

    def finish_shot(self):
        """One photo (a quick burst of frames) is done."""
        self.capturing = False
        self.samples.extend(self.burst)
        self.burst = []
        self.shots_done += 1
        self.progress["value"] = self.shots_done
        if self.shots_done < SHOTS:
            self.fp_btn.config(text=f"Take Photo {self.shots_done + 1}")
            self.fp_text.config(
                text="✓ Photo saved. " + SHOT_PROMPTS[self.shots_done], fg="#047857"
            )
            return
        self.fp_btn.config(text="✓ Photo taken")
        self.show_retake_link()
        dup = self.engine.find_duplicate(self.samples)
        if dup:
            who = self.db.user(dup)
            self.fp_text.config(
                text=f'Already registered as {who["name"] if who else dup} '
                f"({dup}) — cannot register again",
                fg=RED,
            )
        else:
            self.fp_text.config(
                text="Face captured. Now press “Register User”.", fg="#047857"
            )

    def toggle_capture(self):
        if self.capturing:
            return
        if self.shots_done < SHOTS and not self.validate_form():
            self.fp_text.config(
                text="Complete the form correctly before taking the photo", fg=RED
            )
            self.reg_msg.config(
                text="Please fix the highlighted fields first. "
                "The photo can be taken only when the form is valid."
            )
            return
        if self.cam is None:  # camera retry
            if self.start_camera():
                self.reg_loop()
            else:
                self.reg_msg.config(text="Camera still unavailable.")
                return
        self.reg_msg.config(text="")
        if self.shots_done >= SHOTS or self.capturing:
            return  # done (use Retake) or already capturing
        self.burst = []
        self.capturing = True
        self.fp_text.config(
            text="Taking photo… look at the camera, move your head slightly", fg=PRIMARY
        )

    def show_retake_link(self):
        self.retake_lbl.config(text="Retake photo", fg=PRIMARY, cursor="hand2")

    def retake(self):
        """Admin clicked Retake: allowed any number of times."""
        if self.capturing or self.shots_done < SHOTS:
            return
        self.reset_photo()
        self.fp_text.config(
            text="Retake: press Take Photo when you are ready", fg=MUTED
        )

    def reset_photo(self):
        self.samples, self.burst, self.shots_done, self.capturing = [], [], 0, False
        self.progress["value"] = 0
        self.fp_btn.config(text="Take Photo")
        self.retake_lbl.config(text="")
        self.fp_text.config(text=SHOT_PROMPTS[0], fg=MUTED)
        self.reg_msg.config(text="")

    def on_type_change(self):
        """The Programme list depends on the user type (Lecturer and Guest have one choice)."""
        options = PROGRAMMES_BY_TYPE.get(self.r_type.get(), [])
        self.r_prog.set_values(options)
        self.r_prog.set("")  # always starts empty: the person chooses
        self.r_prog.ok()

    def clear_register_form(self):
        for f in (self.r_name, self.r_id, self.r_email, self.r_course):
            f.entry.delete(0, "end")
            f.ok()
        self.r_type.set("")
        self.r_type.ok()
        self.on_type_change()
        self.retakes = 0
        self.reset_photo()
        self.r_name.focus()

    def msg_name(self, v):
        if not v:
            return "Full name is required."
        if not v[0].isalpha() or not v[0].isascii():
            return "Name must start with a letter (A-Z)."
        bad = [c for c in v if not (c.isascii() and c.isalpha()) and c not in " .'-"]
        if bad:
            return f'Letters and spaces only - "{bad[0]}" is not allowed.'
        if len(v) < 3:
            return "Name needs at least 3 characters."
        if len(v) > 60:
            return "Name is too long (maximum 60 characters)."
        return ""

    def msg_id(self, v):
        if not v:
            return "ID is required."
        if not (v[0].isascii() and v[0].isalnum()):
            return "ID must start with a letter or number."
        bad = [c for c in v if not (c.isascii() and c.isalnum()) and c != "-"]
        if bad:
            return f'Only letters, numbers and "-" allowed - "{bad[0]}" is not allowed.'
        if len(v) > 20:
            return "ID is too long (maximum 20 characters)."
        if self.db.uid_taken(v):
            return "This ID is already registered."
        return ""

    def msg_email(self, v):
        if not v:
            return "Email ID is required."
        if " " in v:
            return "Email cannot contain spaces."
        if not (v[0].isascii() and v[0].isalnum()):
            return "Email must start with a letter or number."
        if "@" not in v:
            return 'Email must contain "@", e.g. name@gmail.com.'
        if v.count("@") > 1:
            return 'Email can contain only one "@".'
        local, domain = v.split("@")
        if not local or not re.fullmatch(r"[A-Za-z0-9._%+\-]+", local):
            return 'Part before "@" can use letters, numbers and . _ % + - only.'
        if local.endswith(".") or ".." in v:
            return 'Email cannot have ".." or end the name with ".".'
        if not domain:
            return 'Add the domain after "@", e.g. gmail.com.'
        if "." not in domain:
            return "Domain needs a dot, e.g. gmail.com."
        if not re.fullmatch(r"[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}", domain):
            return "Domain is not valid, e.g. gmail.com."
        if len(v) > 100:
            return "Email is too long (maximum 100 characters)."
        if self.db.email_taken(v):
            return "This email is already registered."
        return ""

    def msg_course(self, v):
        if not v:
            return "Course / Department is required."
        if not (v[0].isascii() and v[0].isalnum()):
            return "Must start with a letter or number."
        bad = [
            c for c in v if not (c.isascii() and c.isalnum()) and c not in " &/.,()-"
        ]
        if bad:
            return f'"{bad[0]}" is not allowed here.'
        if len(v) < 2:
            return "Type at least 2 characters, e.g. ICT."
        if len(v) > 60:
            return "Too long (maximum 60 characters)."
        return ""

    def msg_type(self):
        return "" if self.r_type.get() in PROGRAMMES_BY_TYPE else "Select a user type."

    def msg_prog(self):
        prog, utype = self.r_prog.get(), self.r_type.get()
        if utype not in PROGRAMMES_BY_TYPE:
            return "Select the user type first."
        if not prog:
            return "Select a programme."
        if prog not in PROGRAMMES_BY_TYPE.get(utype, []):
            return f"Not valid for {utype}."
        return ""

    def setup_live_validation(self):
        """Messages appear while typing, from the very first letter."""
        self.r_name.live(self.msg_name, self.refresh_photo_state)
        self.r_id.live(self.msg_id, self.refresh_photo_state)
        self.r_email.live(self.msg_email, self.refresh_photo_state)
        self.r_course.live(self.msg_course, self.refresh_photo_state)
        self.r_prog.box.bind(
            "<<ComboboxSelected>>", lambda e: self.refresh_photo_state(), add="+"
        )
        self.r_type.box.bind(
            "<<ComboboxSelected>>", lambda e: self.refresh_photo_state(), add="+"
        )

    def form_is_valid(self):
        """Silent check (no messages)."""
        return not (
            self.msg_name(self.r_name.get())
            or self.msg_id(self.r_id.get())
            or self.msg_email(self.r_email.get())
            or self.msg_type()
            or self.msg_prog()
            or self.msg_course(self.r_course.get())
        )

    def refresh_photo_state(self):
        """Hint under the camera: tells whether the photo can be taken yet."""
        if getattr(self, "shots_done", 0) >= SHOTS or getattr(self, "capturing", False):
            return
        if self.form_is_valid():
            self.fp_text.config(text="Form is complete - press Take Photo", fg=GREEN)
        else:
            self.fp_text.config(text=SHOT_PROMPTS[0], fg=MUTED)

    def validate_form(self):
        """Check every field. Shows an error under each wrong field. True only if all are valid."""
        valid = True
        for f, fn in (
            (self.r_name, self.msg_name),
            (self.r_id, self.msg_id),
            (self.r_email, self.msg_email),
            (self.r_course, self.msg_course),
        ):
            f.ok()
            m = fn(f.get())
            if m:
                f.error(m)
                valid = False
            else:
                f.good()
        self.r_type.ok()
        m = self.msg_type()
        if m:
            self.r_type.error(m)
            valid = False
        self.r_prog.ok()
        m = self.msg_prog()
        if m:
            self.r_prog.error(m)
            valid = False
        return valid

    def do_register(self):
        self.reg_msg.config(text="")
        if not self.validate_form():
            self.reg_msg.config(text="Please fix the highlighted fields above.")
            return
        name = " ".join(w[:1].upper() + w[1:] for w in self.r_name.get().split())
        uid, email = self.r_id.get(), self.r_email.get().lower()
        prog, course = self.r_prog.get(), self.r_course.get()
        if len(self.samples) < SAMPLES_NEEDED:
            self.reg_msg.config(text="Please take the face photo before registering.")
            return

        # one face = one ID: refuse a face that is already enrolled under another ID
        owner = self.engine.find_duplicate(self.samples)
        if owner:
            who = self.db.user(owner)
            label = f'{who["name"]} ({owner})' if who else owner
            self.reg_msg.config(
                text=f"Blocked: this face is already registered as {label}. "
                "One person can only have one ID."
            )
            self.fp_text.config(text="Duplicate face — registration blocked", fg=RED)
            return

        self.stop_camera()
        self.capturing = False
        self.db.add_user(
            uid, name, prog, self.r_type.get(), len(self.samples), course, email
        )
        self.engine.save(uid, self.samples)
        self.samples = []
        body = self.page_frame(
            "Student Registration",
            "Add a new student, lecturer or guest with live face enrollment",
        )
        cd = card(body, padx=60, pady=30, border="#A7F3D0")
        cd.pack(pady=10, ipadx=100)
        check_circle(cd).pack()
        tk.Label(
            cd, text="Registered Successfully", bg=CARD, fg=INK, font=F(13, "bold")
        ).pack(pady=(14, 2))
        tk.Label(
            cd,
            text=f"{name} ({uid}) added — face recognition is now active for this user",
            bg=CARD,
            fg=MUTED,
            font=F(9),
        ).pack()
        Btn(cd, "View Profile", lambda: self.user_detail(uid), "outline").pack(
            pady=(16, 0), ipadx=20
        )
        Btn(cd, "Register Another", self.page_register, "outline").pack(
            pady=(8, 0), ipadx=20
        )
