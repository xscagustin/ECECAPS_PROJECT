"""
login_page.py - the Login tab (Chapter 4.2.1, "App Login").

What it does:
  1. Asks for a username and password.
  2. Looks the username up in the Staff table (via the shared MySQL cursor).
  3. Compares the salted password hash.
  4. On success, builds the user dict {"id", "name", "role", "department"}
     and hands it to app.py through on_login(). app.py then shows only the
     tabs that role is allowed to use.

Any failure (wrong password, unknown user, database error) means DENY.

Note: unlike the other pages, this one receives two callbacks instead of
`user`, because it is the page that *creates* the user:
    LoginPage(parent, cursor, on_login, on_logout)
"""

import hashlib
import hmac

import customtkinter as ctk
import mysql.connector


def hash_password(salt, password):
    """Salted SHA-256 hash. Use this same function when creating users."""
    return hashlib.sha256((salt + password).encode()).hexdigest()


class LoginPage(ctk.CTkFrame):
    def __init__(self, parent, cursor, on_login, on_logout):
        super().__init__(parent, fg_color="transparent")
        self.cursor = cursor
        self.on_login = on_login      # called with the user dict after sign in
        self.on_logout = on_logout    # called after sign out
        self.signed_in = False

        # --- Widgets ---------------------------------------------------------
        ctk.CTkLabel(self, text="Sign in",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(60, 20))

        self.username = ctk.CTkEntry(self, width=260, placeholder_text="Username")
        self.username.pack(pady=8)

        self.password = ctk.CTkEntry(self, width=260, placeholder_text="Password", show="•")
        self.password.pack(pady=8)
        self.password.bind("<Return>", lambda event: self.button_click())  # Enter = sign in

        self.button = ctk.CTkButton(self, text="Sign in", width=260,
                                    command=self.button_click)
        self.button.pack(pady=16)

        self.status = ctk.CTkLabel(self, text="")   # error / welcome message
        self.status.pack(pady=5)

    def button_click(self):
        """One button: signs in, or signs out if already signed in."""
        if self.signed_in:
            self.sign_out()
        else:
            self.sign_in()

    def sign_in(self):
        username = self.username.get().strip()
        password = self.password.get()

        if not username or not password:
            self.show("Enter a username and password.", "orange")
            return

        # Look the user up. %s keeps user input out of the SQL text itself.
        try:
            self.cursor.execute(
                "SELECT employee_id, full_name, access_level, department, "
                "       salt, password_hash "
                "FROM Staff WHERE username = %s", (username,))
            row = self.cursor.fetchone()
        except mysql.connector.Error:
            self.show("Database error. Access denied.", "red")   # fault -> deny
            return

        # Same message for unknown user and wrong password (don't reveal which).
        if row is None or not hmac.compare_digest(
                hash_password(row[4], password), row[5]):
            self.show("Invalid username or password.", "red")
            return

        user = {"id": row[0], "name": row[1], "role": row[2], "department": row[3]}

        self.signed_in = True
        self.password.delete(0, "end")
        self.username.configure(state="disabled")
        self.password.configure(state="disabled")
        self.button.configure(text="Sign out")
        self.show(f"Welcome, {user['name']} ({user['role']})", "green")
        self.on_login(user)

    def sign_out(self):
        self.signed_in = False
        self.username.configure(state="normal")
        self.password.configure(state="normal")
        self.username.delete(0, "end")
        self.button.configure(text="Sign in")
        self.show("Signed out.", "gray")
        self.on_logout()

    def show(self, text, color):
        """Small helper to update the message under the button."""
        self.status.configure(text=text, text_color=color)
