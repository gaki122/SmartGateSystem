# UserManagement page and account-management UI mixin

import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from smartgate_yolo import (
    BG,
    Btn,
    CARD,
    ComboField,
    F,
    FULL_ACCESS_ROLES,
    FormField,
    MUTED,
    RED,
    ROLES,
    card,
    password_problem,
    username_problem,
)


class UserManagementMixin:

    def page_staff(self):
        if self.role not in FULL_ACCESS_ROLES:
            messagebox.showwarning(
                "Access restricted",
                "Only System Administrator and College Management can manage staff accounts.",
                parent=self,
            )
            return
        body = self.page_frame("Staff Accounts", "People who can log in to Smart Gate")
        top = tk.Frame(body, bg=BG)
        top.pack(fill="x", pady=(0, 10))
        Btn(top, "+  Add staff", self.add_staff_dialog).pack(side="left", ipadx=16)
        tk.Label(
            top,
            text=(
                "System Administrator and College Management have the same full access.  "
                "Security Guards can access the dashboard, face verification, and system reports."
            ),
            bg=BG,
            fg=MUTED,
            font=F(8),
            wraplength=620,
            justify="left",
        ).pack(side="left", padx=14)
        acts = tk.Frame(body, bg=BG)
        acts.pack(side="bottom", fill="x")
        Btn(
            acts, "Change username", lambda: self.staff_action("username"), "outline"
        ).pack(side="left", ipadx=8, padx=(0, 6))
        Btn(acts, "Change role", lambda: self.staff_action("role"), "outline").pack(
            side="left", ipadx=8, padx=(0, 6)
        )
        Btn(acts, "Recovery email", lambda: self.staff_action("email"), "outline").pack(
            side="left", ipadx=8, padx=(0, 6)
        )
        Btn(acts, "Reset password", lambda: self.staff_action("reset"), "outline").pack(
            side="left", ipadx=10, padx=(0, 8)
        )
        Btn(
            acts, "Disable / Enable", lambda: self.staff_action("toggle"), "outline"
        ).pack(side="left", ipadx=12, padx=(0, 8))
        Btn(acts, "Delete", lambda: self.staff_action("delete"), "red").pack(
            side="left", ipadx=12
        )
        tk.Label(
            acts,
            text="Select a person in the table, then choose an action.",
            bg=BG,
            fg=MUTED,
            font=F(8),
        ).pack(side="left", padx=14)
        self.staff_tree = self.make_tree(
            body,
            [
                ("name", "NAME", 180),
                ("user", "USERNAME", 150),
                ("role", "ROLE", 175),
                ("state", "STATUS", 90),
                ("last", "LAST SIGN-IN", 170),
            ],
        )
        for r in self.db.staff_list():
            last = r["last_login"]
            last = (
                datetime.strptime(last, "%Y-%m-%d %H:%M:%S").strftime(
                    "%d %b %Y  %I:%M %p"
                )
                if last
                else "Never"
            )
            you = "  (you)" if r["username"] == self.me["username"] else ""
            self.staff_tree.insert(
                "",
                "end",
                iid=r["username"],
                tags=("in" if r["active"] else "out",),
                values=(
                    r["full_name"] + you,
                    r["username"],
                    r["role"],
                    "Active" if r["active"] else "Disabled",
                    last,
                ),
            )

    def staff_selected(self):
        sel = self.staff_tree.selection()
        if not sel:
            messagebox.showinfo(
                "Staff Accounts", "Select a person in the table first.", parent=self
            )
            return None
        return self.db.staff_get(sel[0])

    def staff_action(self, what):
        if self.role not in FULL_ACCESS_ROLES:
            messagebox.showwarning(
                "Access restricted",
                "Only System Administrator and College Management can manage staff accounts.",
                parent=self,
            )
            return
        r = self.staff_selected()
        if not r:
            return
        me = r["username"] == self.me["username"]
        last_admin = (
            r["role"] in FULL_ACCESS_ROLES
            and r["active"]
            and self.db.active_admins() <= 1
        )
        if what == "reset":
            self.password_dialog(r, own=False)
        elif what == "username":
            self.change_username_dialog(r)
        elif what == "role":
            self.change_role_dialog(r)
        elif what == "email":
            self.change_email_dialog(r)
        elif what == "toggle":
            if me:
                messagebox.showinfo(
                    "Staff Accounts",
                    "You cannot disable your own account.",
                    parent=self,
                )
            elif last_admin:
                messagebox.showinfo(
                    "Staff Accounts",
                    "At least one active full-access account is needed.",
                    parent=self,
                )
            else:
                self.db.set_active(r["username"], not r["active"])
                self.navigate("staff")
        elif what == "delete":
            if me:
                messagebox.showinfo(
                    "Staff Accounts", "You cannot delete your own account.", parent=self
                )
            elif last_admin:
                messagebox.showinfo(
                    "Staff Accounts",
                    "At least one active full-access account is needed.",
                    parent=self,
                )
            elif messagebox.askyesno(
                "Delete account",
                f'Delete the account of {r["full_name"]} ({r["username"]})?\n'
                "This cannot be undone.",
                parent=self,
            ):
                self.db.delete_staff(r["username"])
                self.navigate("staff")

    def change_username_dialog(self, row):
        """Only a full-access role can change a staff username."""
        if self.role not in FULL_ACCESS_ROLES:
            messagebox.showwarning(
                "Access restricted",
                "Only System Administrator and College Management can change usernames.",
                parent=self,
            )
            return
        top = self.popup("Change username", f'Account: {row["full_name"]}', 430, 300)
        cd = card(top.content, padx=24, pady=12)
        cd.pack(fill="x", padx=22)
        field = FormField(cd, "New Username", wrap=350)
        field.pack(fill="x")
        field.entry.insert(0, row["username"])
        msg = tk.Label(
            cd, text="", bg=CARD, fg=RED, font=F(8), wraplength=350, justify="left"
        )
        msg.pack(anchor="w", pady=(4, 0))

        def save():
            new_name = field.get().strip().lower()
            problem = username_problem(new_name)
            existing = self.db.staff_get(new_name)
            if problem:
                field.error(problem)
                return
            if existing and new_name != row["username"].lower():
                field.error("This username is already taken.")
                return
            if new_name == row["username"].lower():
                top.destroy()
                return
            old_name = row["username"]
            try:
                self.db.set_username(old_name, new_name)
            except sqlite3.IntegrityError:
                field.error("This username is already taken.")
                return
            if old_name == self.me["username"]:
                self.me = self.db.staff_get(new_name)
            top.destroy()
            self.navigate("staff")
            messagebox.showinfo(
                "Username updated", f"Username changed to {new_name}.", parent=self
            )

        Btn(cd, "Save username", save).pack(fill="x", pady=(10, 4))
        field.focus()

    def change_role_dialog(self, row):
        """Only a full-access role can change staff roles."""
        if self.role not in FULL_ACCESS_ROLES:
            messagebox.showwarning(
                "Access restricted",
                "Only System Administrator and College Management can change staff roles.",
                parent=self,
            )
            return
        if row["username"] == self.me["username"]:
            messagebox.showinfo(
                "Change role",
                "You cannot change your own role while signed in.",
                parent=self,
            )
            return
        if (
            row["role"] in FULL_ACCESS_ROLES
            and row["active"]
            and self.db.active_admins() <= 1
        ):
            messagebox.showinfo(
                "Change role",
                "At least one active full-access account must remain.",
                parent=self,
            )
            return
        top = self.popup(
            "Change staff role",
            f'Account: {row["full_name"]} ({row["username"]})',
            430,
            260,
        )
        cd = card(top.content, padx=24, pady=12)
        cd.pack(fill="x", padx=22)
        role = ComboField(cd, "New Role", ROLES)
        role.pack(fill="x")
        role.set(row["role"])

        def save():
            new_role = role.get()
            if new_role not in ROLES:
                role.error("Choose a role.")
                return
            if new_role == row["role"]:
                top.destroy()
                return
            self.db.set_role(row["username"], new_role)
            top.destroy()
            self.navigate("staff")
            messagebox.showinfo(
                "Role updated", f'{row["full_name"]} is now {new_role}.', parent=self
            )

        Btn(cd, "Save role", save).pack(fill="x", pady=(12, 4))

    def add_staff_dialog(self):
        if self.role not in FULL_ACCESS_ROLES:
            messagebox.showwarning(
                "Access restricted",
                "Only System Administrator and College Management can add staff accounts.",
                parent=self,
            )
            return
        top = self.popup(
            "Add staff account",
            "They will log in with this username and password.",
            470,
            720,
        )
        cd = card(top.content, padx=24, pady=10)
        cd.pack(fill="x", padx=22)
        f_name = FormField(cd, "Full Name", wrap=380)
        f_user = FormField(cd, "Username", hint="e.g. pema.guard", wrap=380)
        role = ComboField(cd, "Role", ROLES)
        role.err.config(wraplength=380)
        f_pw = FormField(
            cd,
            "Password",
            show="•",
            hint="8+ characters, letters and numbers",
            wrap=380,
        )
        f_pw2 = FormField(cd, "Confirm Password", show="•", wrap=380)
        f_email = FormField(
            cd, "Email (for password recovery)", hint="e.g. name@gmail.com", wrap=380
        )
        for f in (f_name, f_user, role, f_pw, f_pw2, f_email):
            f.pack(fill="x")
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
            cd, text="", bg=CARD, fg=RED, font=F(8), wraplength=380, justify="left"
        )
        msg.pack(anchor="w", pady=(6, 0))

        def save():
            ok = True
            for f, fn in (
                (f_name, self.msg_name),
                (f_user, lambda v: self.msg_username(v.lower())),
                (f_pw, password_problem),
                (f_pw2, confirm_msg),
                (f_email, self.msg_staff_email),
            ):
                m = fn(f.get())
                if m:
                    f.error(m)
                    ok = False
                else:
                    f.good()
            role.ok()
            if role.get() not in ROLES:
                role.error("Choose a role.")
                ok = False
            if not ok:
                msg.config(text="Please fix the highlighted fields.")
                return
            name = " ".join(w[:1].upper() + w[1:] for w in f_name.get().split())
            self.db.add_staff(
                f_user.get().lower(),
                name,
                role.get(),
                f_pw.get(),
                f_email.get().lower(),
            )
            top.destroy()
            self.navigate("staff")
            messagebox.showinfo(
                "Account created",
                f"{name} can now log in as {f_user.get().lower()}.",
                parent=self,
            )

        Btn(cd, "Create account", save).pack(fill="x", pady=(8, 4))
        f_name.focus()

    def password_dialog(self, row, own=False):
        """Reset a staff password; this dialog is restricted to full-access roles."""
        if self.role not in FULL_ACCESS_ROLES:
            messagebox.showwarning(
                "Access restricted",
                "Only System Administrator and College Management can reset staff passwords.",
                parent=self,
            )
            return
        own = False
        title = "Reset password"
        sub = (
            "Choose a new password for your account."
            if own
            else f'New password for {row["full_name"]} ({row["username"]}).'
        )
        top = self.popup(title, sub, 460, 520 if own else 450)
        cd = card(top.content, padx=24, pady=10)  # was card(top): the form was hidden
        cd.pack(fill="x", padx=22)
        f_old = FormField(cd, "Current Password", show="•", wrap=380) if own else None
        f_pw = FormField(
            cd,
            "New Password",
            show="•",
            hint="8+ characters, letters and numbers",
            wrap=380,
        )
        f_pw2 = FormField(cd, "Confirm New Password", show="•", wrap=380)
        for f in (f_old, f_pw, f_pw2):
            if f:
                f.pack(fill="x")
        confirm_msg = lambda v: (
            "Type the password again."
            if not v
            else "" if v == f_pw.entry.get().strip() else "Passwords do not match."
        )
        f_pw.live(password_problem, lambda: f_pw2.check_now() if f_pw2.get() else None)
        f_pw2.live(confirm_msg)

        def save():
            ok = True
            if f_old is not None:
                if not f_old.entry.get():
                    f_old.error("Enter your current password.")
                    ok = False
                elif not self.db.check_password(row["username"], f_old.entry.get()):
                    f_old.error("Current password is wrong.")
                    ok = False
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
            top.destroy()
            messagebox.showinfo(
                "Password updated", "The password was changed.", parent=self
            )

        Btn(cd, "Save password", save).pack(fill="x", pady=(14, 4))
        (f_old or f_pw).focus()
