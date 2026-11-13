

import os
import shutil
import sys
 
HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "smartgate_yolo.py")
 
WELCOME_CODE = '''    # ------------------------------------------------------------------
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
            cv.create_text(cx, int(h * 0.40), text="Learn  \\u2022  Teach  \\u2022  Empower",
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
            cv.create_text(cx, h * 0.955, text="\\u00a9 2026 Samtse College of Education",
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
            text="\\u2190 Back to Home",
            bg=NAVY,
            fg="#DCE8F3",
            font=F(9, "bold"),
            cursor="hand2",
        )
        back.pack(side="left", pady=8)
        back.bind("<Button-1>", lambda _event: self.show_welcome())
        back.bind("<Enter>", lambda _event: back.config(fg="white"))
        back.bind("<Leave>", lambda _event: back.config(fg="#DCE8F3"))

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
            text="A tradition of teacher education  \\u2022  Samtse, Bhutan",
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
                "<MouseWheel>", lambda event: canvas.yview_scroll(
                    int(-event.delta / 120), "units"
                )
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
            text="SAMTSE  \\u2022  BHUTAN",
            fill="#FACC15",
            font=F(9, "bold"),
        )
        banner_title = campus_banner.create_text(
            1,
            1,
            anchor="nw",
            width=300,
            text="A place for\\nlearning",
            fill="white",
            font=("Georgia", 24, "bold"),
            justify="left",
        )
        banner_caption = campus_banner.create_text(
            1,
            1,
            anchor="nw",
            width=300,
            text="Samtse College of Education\\nA view of the campus",
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
            ("01", "Teacher education",
             "Preparing educators with the knowledge and skills to guide learning.", PRIMARY),
            ("02", "Teaching & learning",
             "Encouraging thoughtful teaching and positive learning experiences.", GREEN),
            ("03", "Research & service",
             "Learning from inquiry and contributing through service to education.", "#D97706"),
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
            text="College history and programme information  \\u2022  SCE official website",
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
            text="\\u00a9 2026 Samtse College of Education",
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
 
'''
 
BACK_LINK = '''        back = tk.Label(left, text="\\u2190 Back to Home", bg=LB, fg=PRIMARY,
                        font=F(9, "bold"), cursor="hand2")
        back.place(relx=1.0, x=-24, y=24, anchor="ne")
        back.bind("<Button-1>", lambda e: self.show_welcome())
'''
 
 
def stop(msg):
    print("\nSTOPPED - nothing was changed.\n" + msg)
    sys.exit(1)
 
 
def main():
    if not os.path.isfile(TARGET):
        stop("smartgate_yolo.py was not found next to this script.")
    with open(TARGET, encoding="utf-8") as f:
        src = f.read()
    if "def show_welcome" in src:
        stop("The welcome screen is already in smartgate_yolo.py (maybe pasted earlier).\n"
             "Use a clean copy of smartgate_yolo.py, then run this again.")
 
    # 1) insert the welcome screen code just above show_login
    a1 = "    def show_login(self):"
    if src.count(a1) != 1:
        stop("Could not find 'def show_login(self):' exactly once.")
    src = src.replace(a1, WELCOME_CODE + a1)
 
    # 2) open the welcome screen at start-up (end of _wait_engine)
    old2 = ("        if self.db.staff_count() == 0:\n"
            "            self.show_setup()\n"
            "        else:\n"
            "            self.show_login()\n")
    if src.count(old2) != 1:
        stop("Could not find the end of _wait_engine (the if/else that opens login).")
    src = src.replace(old2, "        self.show_welcome()\n")
 
    # 3) log out -> welcome screen
    i = src.find("    def do_logout(self):")
    if i < 0:
        stop("Could not find do_logout.")
    j = src.find("self.show_login()", i)
    k = src.find("    def navigate", i)
    if j < 0 or (k > 0 and j > k):
        stop("Could not find self.show_login() inside do_logout.")
    src = src[:j] + "self.show_welcome()" + src[j + len("self.show_login()"):]
 
    # 4) "Back to Home" link on the login / sign-up pages
    a4 = '        ).place(relx=0.5, rely=0.975, anchor="center")\n'
    if src.count(a4) != 1:
        stop("Could not find the footer label in auth_layout.")
    src = src.replace(a4, a4 + BACK_LINK)
 
    shutil.copyfile(TARGET, TARGET + ".bak")
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(src)
    print("Done! Welcome screen added.")
    print("Backup saved as smartgate_yolo.py.bak")
    print("Now run:  python smartgate_yolo.py")
 
 
if __name__ == "__main__":
    main()
 
