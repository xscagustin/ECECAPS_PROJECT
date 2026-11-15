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
      user   : dict with "id", "name" and "role"

To add a page: create its file, import its class below, and add one line
to PAGES. Nothing else in this file needs to change.
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
from package_monitor import PackageMonitorPage
# from inventory_terminal import InventoryTerminalPage
from package_receive import PackageReceivePage
# from holds_review import HoldsReviewPage
# from audit_log import AuditLogPage

# Tabs are shown in this order: (tab title, page class).
# Later you can filter this list by CURRENT_USER["role"] so each access level
# only sees its own pages (see Chapter 4.2.1).
PAGES = [
    ("Package Monitor", PackageMonitorPage),
    # ("Inventory Terminal", InventoryTerminalPage),
    ("Package Receive", PackageReceivePage),
    # ("Holds & Review", HoldsReviewPage),
    # ("Audit Log", AuditLogPage),
]

# =============================================================================
# CONFIG
# =============================================================================

# --- Database connection ---
DB = dict(host="127.0.0.1", port=3306, user="root", password="1212",
          database="HospitalDatabase")

# --- Logged-in user (placeholder until the login page passes this in) ---
CURRENT_USER = {"id": "AD-032", "name": "A. Patel",
                "role": "Administrative", "department": "Pharmacy"}

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

        self.user = CURRENT_USER

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

        ctk.CTkLabel(bar, text=f"{self.user['name']}  "
                               f"({self.user['id']} · {self.user['role']})",
                     text_color=COLORS["header_text"]
                     ).pack(side="right", padx=20)

    def build_pages(self):
        """Create one tab per entry in PAGES and put the page inside it."""
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=12)

        for title, page_class in PAGES:
            tab = self.tabs.add(title)
            page = page_class(tab, self.cursor, self.user)
            page.pack(fill="both", expand=True)

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
