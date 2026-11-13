# Dashboard page

import tkinter as tk
from datetime import datetime

from smartgate_yolo import (
    BG,
    CARD,
    F,
    FIELD,
    GREEN,
    INK,
    MUTED,
    PRIMARY,
    card,
    clickable,
    now,
)


class DashboardMixin:

    def page_dashboard(self):
        body = self.page_frame(
            "Dashboard", "Samtse College of Education — Gate Overview"
        )
        c = self.db.counts()
        today_logs = self.db.today_logs()
        today_entries = [l for l in today_logs if l["action"] == "Entry"]
        today_exits = [l for l in today_logs if l["action"] == "Exit"]

        greet = tk.Frame(body, bg=BG)
        greet.pack(fill="x", pady=(0, 14))
        hour = now().hour
        salute = (
            "Good morning"
            if hour < 12
            else "Good afternoon" if hour < 18 else "Good evening"
        )
        tk.Label(
            greet,
            text=f'{salute}, {self.me["full_name"].split()[0]}.',
            bg=BG,
            fg=INK,
            font=F(12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            greet,
            text=now().strftime("%A, %d %B %Y") + "  ·  figures update live",
            bg=BG,
            fg=MUTED,
            font=F(8),
        ).pack(anchor="w")

        row = tk.Frame(body, bg=BG)
        row.pack(fill="x")
        kinds = [
            (
                "Total Registered",
                c["total"],
                PRIMARY,
                lambda: self.users_dialog("Registered Users", self.users_where("all")),
            ),
            (
                "Currently Inside",
                c["inside"],
                GREEN,
                lambda: self.users_dialog(
                    "Currently Inside", self.users_where("inside")
                ),
            ),
            (
                "Students Inside",
                c["students"],
                "#F59E0B",
                lambda: self.users_dialog(
                    "Students Inside", self.users_where("inside", "Student")
                ),
            ),
            (
                "Lecturers Inside",
                c["lecturers"],
                "#8B5CF6",
                lambda: self.users_dialog(
                    "Lecturers Inside", self.users_where("inside", "Lecturer")
                ),
            ),
        ]
        for i, (lab, val, col, cmd) in enumerate(kinds):
            row.columnconfigure(i, weight=1, uniform="s")
            k = card(row, padx=16, pady=12)
            k.grid(row=0, column=i, sticky="ew", padx=6)
            tk.Label(k, text=lab, bg=CARD, fg=MUTED, font=F(9)).pack(anchor="w")
            v = tk.Frame(k, bg=CARD)
            v.pack(anchor="w")
            tk.Label(v, text="●", bg=CARD, fg=col, font=F(8)).pack(side="left")
            tk.Label(v, text=str(val), bg=CARD, fg=INK, font=F(20, "bold")).pack(
                side="left", padx=6
            )
            tk.Label(k, text="View list →", bg=CARD, fg=PRIMARY, font=F(8)).pack(
                anchor="w"
            )
            clickable(k, cmd)

        row2 = tk.Frame(body, bg=BG)
        row2.pack(fill="x", pady=(10, 0))
        kinds2 = [
            (
                "Today's Entries",
                len(today_entries),
                "#0EA5E9",
                lambda: self.logs_dialog(
                    "Today's Entries", self.db.logs_full(action="Entry")
                ),
            ),
            (
                "Today's Exits",
                len(today_exits),
                "#F97316",
                lambda: self.logs_dialog(
                    "Today's Exits", self.db.logs_full(action="Exit")
                ),
            ),
            (
                "Currently Outside",
                c["total"] - c["inside"],
                MUTED,
                lambda: self.users_dialog(
                    "Currently Outside",
                    [
                        u
                        for u in self.db.users()
                        if self.db.status(u["uid"]) != "Inside"
                    ],
                ),
            ),
            (
                "Registered Guests",
                c["reg_guests"],
                "#EC4899",
                lambda: self.users_dialog(
                    "Registered Guests", self.users_where("all", "Guest")
                ),
            ),
        ]
        for i, (lab, val, col, cmd) in enumerate(kinds2):
            row2.columnconfigure(i, weight=1, uniform="s2")
            k = card(row2, padx=16, pady=10)
            k.grid(row=0, column=i, sticky="ew", padx=6)
            tk.Label(k, text=lab, bg=CARD, fg=MUTED, font=F(8)).pack(anchor="w")
            v = tk.Frame(k, bg=CARD)
            v.pack(anchor="w")
            tk.Label(v, text="●", bg=CARD, fg=col, font=F(7)).pack(side="left")
            tk.Label(v, text=str(val), bg=CARD, fg=INK, font=F(15, "bold")).pack(
                side="left", padx=5
            )
            clickable(k, cmd)

        tk.Label(
            body, text="Occupancy Breakdown", bg=BG, fg=INK, font=F(11, "bold")
        ).pack(anchor="w", pady=(20, 10))
        bp = tk.Frame(body, bg=BG)
        bp.pack(fill="x")
        bp.columnconfigure((0, 1), weight=1, uniform="bp")

        def dbar(parent, label, val, mx, color, right, cmd):
            r = tk.Frame(parent, bg=CARD)
            r.pack(fill="x", pady=5)
            top = tk.Frame(r, bg=CARD)
            top.pack(fill="x")
            tk.Label(top, text=label, bg=CARD, fg=MUTED, font=F(8)).pack(side="left")
            tk.Label(top, text=right, bg=CARD, fg=INK, font=F(8, "bold")).pack(
                side="right"
            )
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
            clickable(r, cmd)

        p1 = card(bp, padx=16, pady=14)
        p1.grid(row=0, column=0, sticky="new", padx=(0, 6))
        tk.Label(
            p1, text="REGISTERED USERS BY TYPE", bg=CARD, fg=INK, font=F(8, "bold")
        ).pack(anchor="w", pady=(0, 6))
        mxr = max(c["total"], 1)
        dbar(
            p1,
            "Student",
            c["reg_students"],
            mxr,
            PRIMARY,
            str(c["reg_students"]),
            lambda: self.users_dialog(
                "Registered Students", self.users_where("all", "Student")
            ),
        )
        dbar(
            p1,
            "Lecturer",
            c["reg_lecturers"],
            mxr,
            "#8B5CF6",
            str(c["reg_lecturers"]),
            lambda: self.users_dialog(
                "Registered Lecturers", self.users_where("all", "Lecturer")
            ),
        )
        if c["reg_guests"]:
            dbar(
                p1,
                "Guest",
                c["reg_guests"],
                mxr,
                "#EC4899",
                str(c["reg_guests"]),
                lambda: self.users_dialog(
                    "Registered Guests", self.users_where("all", "Guest")
                ),
            )

        p2 = card(bp, padx=16, pady=14)
        p2.grid(row=0, column=1, sticky="new", padx=(6, 0))
        tk.Label(
            p2, text="CURRENTLY INSIDE BY TYPE", bg=CARD, fg=INK, font=F(8, "bold")
        ).pack(anchor="w", pady=(0, 6))
        dbar(
            p2,
            "Student",
            c["students"],
            max(c["reg_students"], 1),
            GREEN,
            f'{c["students"]} / {c["reg_students"]}',
            lambda: self.users_dialog(
                "Students Inside", self.users_where("inside", "Student")
            ),
        )
        dbar(
            p2,
            "Lecturer",
            c["lecturers"],
            max(c["reg_lecturers"], 1),
            GREEN,
            f'{c["lecturers"]} / {c["reg_lecturers"]}',
            lambda: self.users_dialog(
                "Lecturers Inside", self.users_where("inside", "Lecturer")
            ),
        )
        if c["reg_guests"]:
            dbar(
                p2,
                "Guest",
                c["in_guests"],
                c["reg_guests"],
                GREEN,
                f'{c["in_guests"]} / {c["reg_guests"]}',
                lambda: self.users_dialog(
                    "Guests Inside", self.users_where("inside", "Guest")
                ),
            )

        tk.Label(
            body, text="Operational Control Actions", bg=BG, fg=INK, font=F(11, "bold")
        ).pack(anchor="w", pady=(20, 10))
        grid = tk.Frame(body, bg=BG)
        grid.pack(fill="x")
        actions = [
            (
                "Face Verification",
                "Open the live camera and verify a registered person by face",
                "☺",
                "verify",
                PRIMARY,
            ),
            (
                "Student Registration",
                "Enroll a new student, lecturer or guest with live face capture",
                "✚",
                "register",
                GREEN,
            ),
            (
                "View Records",
                "Audit past logs, timestamps, direction status of access events",
                "☰",
                "records",
                "#F59E0B",
            ),
            (
                "System Reports",
                "Extract hourly gate transit charts, campus occupancy distributions",
                "▮",
                "reports",
                "#8B5CF6",
            ),
        ]
        slot = 0
        for title, desc, ic, page, col in actions:
            if not self.can_access_page(page):
                continue
            grid.columnconfigure(slot % 2, weight=1, uniform="a")
            a = card(grid, padx=16, pady=14)
            a.grid(row=slot // 2, column=slot % 2, sticky="ew", padx=6, pady=6)
            slot += 1
            tk.Label(a, text=ic, bg=CARD, fg=col, font=F(16), width=2).pack(
                side="left", anchor="n"
            )
            t = tk.Frame(a, bg=CARD)
            t.pack(side="left", padx=10)
            tk.Label(t, text=title, bg=CARD, fg=INK, font=F(10, "bold")).pack(
                anchor="w"
            )
            tk.Label(
                t,
                text=desc,
                bg=CARD,
                fg=MUTED,
                font=F(8),
                wraplength=260,
                justify="left",
            ).pack(anchor="w")
            clickable(a, lambda p=page: self.navigate(p))

        tk.Label(
            body,
            text="Recent Gate Activity  (click a row for the profile)",
            bg=BG,
            fg=INK,
            font=F(11, "bold"),
        ).pack(anchor="w", pady=(16, 8))
        ra = card(body)
        ra.pack(fill="x", padx=6)
        recent = self.db.recent_logs(4)
        if not recent:
            tk.Label(
                ra, text="No activity recorded yet.", bg=CARD, fg=MUTED, font=F(9)
            ).pack(pady=14)
        for l in recent:
            dt = datetime.strptime(l["ts"], "%Y-%m-%d %H:%M:%S")
            entry = l["action"] == "Entry"
            r = tk.Frame(ra, bg=CARD, padx=14, pady=7)
            r.pack(fill="x")
            tk.Label(
                r,
                text="↓ Entry" if entry else "↑ Exit",
                bg=CARD,
                width=8,
                anchor="w",
                fg="#047857" if entry else "#B45309",
                font=F(9, "bold"),
            ).pack(side="left")
            tk.Label(r, text=l["name"], bg=CARD, fg=INK, font=F(9, "bold")).pack(
                side="left"
            )
            tk.Label(
                r, text=f'  {l["type"]} · {l["uid"]}', bg=CARD, fg=MUTED, font=F(8)
            ).pack(side="left")
            tk.Label(
                r, text=dt.strftime("%d/%m  %I:%M %p"), bg=CARD, fg=MUTED, font=F(8)
            ).pack(side="right")
            clickable(r, lambda uid=l["uid"]: self.user_detail(uid), tint=True)
        self.later(10000, self.page_dashboard)  # live auto-refresh
