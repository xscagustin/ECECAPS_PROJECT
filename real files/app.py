"""
Hospital IAM Sorting Hub - main app (run this file)

app.py owns everything shared between pages:
  - the window and header bar
  - the MySQL connection
  - the logged-in user
  - the look of the tables
  - the list of pages (PAGES below)

Each page lives in its own file as a frame class that is created like this:
    PageClass(parent, cursor, user)
      parent : the tab the page is placed in
      cursor : the shared MySQL cursor
      user   : dict with "id", "name", "role" and "department"

The Login tab is the one exception: it creates the user, so it gets
callbacks instead (see login_page.py).

To add a page: create its file, import its class below, add one line to
PAGES, and add its title to the roles allowed to see it in ROLE_PAGES.
"""

# --- Compatibility shim (kept from test.py) ---------------------------------
# Must stay above any import that loads mysql.connector.
import ssl

for name in ("PROTOCOL_TLSv1", "PROTOCOL_TLSv1_1", "PROTOCOL_TLSv1_2"):
    if not hasattr(ssl, name):
        setattr(ssl, name, ssl.PROTOCOL_TLS)

from tkinter import ttk
import customtkinter as ctk
import mysql.connector

# --- Pages -------------------------------------------------------------------
# One import per page file. Uncomment the others as you create them.
from login_page import LoginPage                      # <-- NEW
from package_monitor import PackageMonitorPage
from inventory_terminal import InventoryTerminalPage
from package_receive import PackageReceivePage
from holds_review import HoldsReviewPage
from audit_log import AuditLogPage

# Pages shown AFTER login, in this order: (tab title, page class).
PAGES = [
    ("Package Monitor", PackageMonitorPage),
    ("Inventory Terminal", InventoryTerminalPage),
    ("Package Receive", PackageReceivePage),
    ("Holds & Review", HoldsReviewPage),
    ("Audit Log", AuditLogPage),
]

# <-- NEW: which tabs each access level may see (Chapter 4.1.3 / 4.2.1).
ROLE_PAGES = {
    "Medical Staff":  [],
    "Departmental":   ["Package Monitor", "Package Receive", "Holds & Review"],
    "Courier":        ["Package Monitor", "Inventory Terminal"],
    "Administrative": ["Package Monitor", "Package Receive", "Holds & Review",
                       "Audit Log", "Inventory Terminal"],
}

# =============================================================================
# CONFIG
# =============================================================================

# --- Database connection ---
DB = dict(host="127.0.0.1", port=3306, user="root", password="1212",
          database="HospitalDatabase")

# --- Colours for the window and header ---
COLORS = {
    "primary": "#0f766e",
    "header_text": "#ffffff",
    "page_bg": "#f3f6f8",
}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Hospital IAM Sorting Hub")
        self.geometry("1150x750")
        self.configure(fg_color=COLORS["page_bg"])

        # One database connection shared by every page
        self.cnx = mysql.connector.connect(**DB)
        self.cnx.autocommit = True        # so pages always see the latest data
        self.cursor = self.cnx.cursor()

        self.user = None                  # <-- CHANGED: set by the login page
        self.page_tabs = []               # <-- NEW: titles of tabs added after login

        self.build_header()
        self.style_tables()
        self.build_pages()

    def build_header(self):
        """Top bar: app name on the left, signed-in user on the right."""
        bar = ctk.CTkFrame(self, fg_color=COLORS["primary"], corner_radius=0)
        bar.pack(fill="x")

        ctk.CTkLabel(bar, text="Hospital IAM Sorting Hub",
                     text_color=COLORS["header_text"],
                     font=ctk.CTkFont(size=16, weight="bold")
                     ).pack(side="left", padx=20, pady=10)
        ctk.CTkLabel(bar, text="Local network · Sample data",
                     text_color="#b6e3de").pack(side="left")

        # <-- CHANGED: kept as self.user_label so login/logout can update it
        self.user_label = ctk.CTkLabel(bar, text="Not signed in",
                                       text_color=COLORS["header_text"])
        self.user_label.pack(side="right", padx=20)

    def build_pages(self):
        """Start with only the Login tab. Other tabs are added after sign in."""
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=12)

        login_tab = self.tabs.add("Login")                     # <-- NEW
        LoginPage(login_tab, self.cursor,
                  self.on_login, self.on_logout).pack(fill="both", expand=True)

    def on_login(self, user):
        """<-- NEW: called by the login page. Adds the tabs this role may use."""
        self.user = user
        self.user_label.configure(
            text=f"{user['name']}  ({user['id']} · {user['role']})")

        allowed = ROLE_PAGES.get(user["role"], [])
        for title, page_class in PAGES:
            if title in allowed:
                tab = self.tabs.add(title)
                page_class(tab, self.cursor, user).pack(fill="both", expand=True)
                self.page_tabs.append(title)

        if self.page_tabs:
            self.tabs.set(self.page_tabs[0])   # jump to the first page

    def on_logout(self):
        """<-- NEW: called by the login page. Removes every non-login tab."""
        for title in self.page_tabs:
            self.tabs.delete(title)
        self.page_tabs = []
        self.user = None
        self.user_label.configure(text="Not signed in")

    def style_tables(self):
        """Make the plain Tk tables (used by every page) match the window."""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10),
                        background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"),
                        background="#e2e8ec", relief="flat")
        style.map("Treeview", background=[("selected", COLORS["primary"])],
                  foreground=[("selected", "white")])


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    App().mainloop()