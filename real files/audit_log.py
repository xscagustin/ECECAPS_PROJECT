"""
Audit Log page (a frame that app.py places inside its main window)
 
Admin-only page. Tab 1 ("Request History") reads ONLY from the AuditLog table
and shows, for each logged decision:
  - Approval : Approved / Denied   (worked out from the "decision" column)
  - Delivery : Delivered / Missing / In progress / On hold / Pending
               (worked out from the "state" column)
 
AuditLog columns used:
    log_id, timestamp, employee_id, request_id, decision, reason, state
 
How app.py uses this file:
    AuditLogPage(parent, cursor, user)
      parent : the tab the page is placed in
      cursor : the shared MySQL cursor created by app.py
      user   : dict with "id", "name", "role" and "department"
"""
 
from tkinter import ttk, W
import customtkinter as ctk
 
# =============================================================================
# CONFIG
# =============================================================================
 
# AuditLog.decision  ->  Approval text shown in the table
APPROVAL_OF_DECISION = {
    "Approval":    "Approved",
    "Disapproval": "Denied",
}
 
# AuditLog.state  ->  Delivery text shown in the table
DELIVERY_OF_STATE = {
    "Delivered":   "Delivered",
    "Missing":     "Missing",
    "In Progress": "In progress",
    "On Hold":     "On hold",
    "Pending":     "Pending",
    "Denied":      "-",           # a denied request is never delivered
}
 
# Dropdown choices. Each one matches either the Approval or the Delivery text.
FILTER_OPTIONS = ["All entries", "Approved", "Denied", "Pending",
                  "In progress", "Delivered", "Missing", "On hold"]
 
# Row colour by Delivery text, or by Approval text if Delivery has no colour
ROW_COLORS = {
    "Denied":      "#fee2e2",   # red
    "Missing":     "#fecaca",   # darker red
    "On hold":     "#fef3c7",   # amber
    "Pending":     "#e0f2fe",   # blue
    "In progress": "#e0f2fe",   # blue
    "Delivered":   "#dcfce7",   # green
}
 
# (heading, width in pixels) for each column of the table
COLUMNS = [
    ("Log ID", 55), ("Timestamp", 120), ("Employee", 85), ("Request", 75),
    ("Approval", 85), ("Delivery", 90), ("Reason", 220),
]
 
PAGE_SIZE = 12
PRIMARY = "#0f766e"
 
 
# =============================================================================
# The page
# =============================================================================
class AuditLogPage(ctk.CTkFrame):
    def __init__(self, master, cursor, user):
        super().__init__(master, fg_color="transparent")
        self.cursor = cursor
        self.user = user
        self.page = 0
 
        # Page title
        ctk.CTkLabel(self, text="Audit Log", anchor="w",
                     font=ctk.CTkFont(size=22, weight="bold")
                     ).pack(fill="x", padx=10, pady=(4, 0))
 
        # Only administrators may view this page
        if user["role"] != "Administrative":
            ctk.CTkLabel(self, text="Access denied: administrators only.",
                         text_color="#b91c1c").pack(pady=40)
            return
 
        ctk.CTkLabel(self, text="Past decisions, approvals and delivery status",
                     anchor="w", text_color="gray40"
                     ).pack(fill="x", padx=10)
 
        # Tabs inside this page (add more tabs here later)
        self.tabs = ctk.CTkTabview(self, fg_color="white")
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.build_history_tab(self.tabs.add("Request History"))
 
        self.load()
 
    # ------------------------------------------------------------ layout ---
    def build_history_tab(self, tab):
        """Search box, filter dropdown, table and page buttons."""
        # top bar
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))
 
        self.search_entry = ctk.CTkEntry(
            top, width=240, placeholder_text="Search request, employee, reason")
        self.search_entry.pack(side="left", padx=(0, 8))
        self.search_entry.bind("<Return>", lambda e: self.apply_filters())
 
        self.filter_box = ctk.CTkComboBox(
            top, values=FILTER_OPTIONS, width=140, state="readonly",
            command=lambda value: self.apply_filters())
        self.filter_box.set(FILTER_OPTIONS[0])
        self.filter_box.pack(side="left", padx=(0, 8))
 
        ctk.CTkButton(top, text="Search", width=80, fg_color=PRIMARY,
                      command=self.apply_filters).pack(side="left")
        ctk.CTkButton(top, text="Refresh", width=80, fg_color=PRIMARY,
                      command=self.load).pack(side="left", padx=8)
 
        self.count_label = ctk.CTkLabel(top, text="")
        self.count_label.pack(side="right")
 
        # table
        names = [c[0] for c in COLUMNS]
        self.tree = ttk.Treeview(tab, columns=names, show="headings",
                                 height=PAGE_SIZE)
        for title, width in COLUMNS:
            self.tree.heading(title, text=title, anchor=W)
            self.tree.column(title, width=width, anchor=W, stretch=True)
        self.tree.pack(fill="both", expand=True)
 
        for tag, color in ROW_COLORS.items():
            self.tree.tag_configure(tag, background=color)
 
        # prev / page label / next
        bottom = ctk.CTkFrame(tab, fg_color="transparent")
        bottom.pack(pady=8)
        self.prev_button = ctk.CTkButton(bottom, text="Prev", width=80,
                                         fg_color=PRIMARY, command=self.prev_page)
        self.prev_button.pack(side="left", padx=8)
        self.page_label = ctk.CTkLabel(bottom, text="Page 1 of 1")
        self.page_label.pack(side="left", padx=8)
        self.next_button = ctk.CTkButton(bottom, text="Next", width=80,
                                         fg_color=PRIMARY, command=self.next_page)
        self.next_button.pack(side="left", padx=8)
 
    # -------------------------------------------------------------- data ---
    def load(self):
        """Read the AuditLog table, filter it and show the current page."""
        # 1. Get every log entry, newest first
        self.cursor.execute(
            "SELECT log_id, timestamp, employee_id, request_id, decision, "
            "reason, state FROM AuditLog ORDER BY timestamp DESC, log_id DESC")
        rows = self.cursor.fetchall()
 
        # 2. Work out Approval and Delivery, and apply search + filter
        search = self.search_entry.get().strip().lower()
        choice = self.filter_box.get()
        shown = []
        for log_id, stamp, employee, request, decision, reason, state in rows:
            approval = APPROVAL_OF_DECISION.get(decision, decision)
            delivery = DELIVERY_OF_STATE.get(state, state or "-")
 
            # search looks in request ID, employee ID and reason
            text = f"{request} {employee} {reason}".lower()
            if search and search not in text:
                continue
            if choice != FILTER_OPTIONS[0] and choice not in (approval, delivery):
                continue
            shown.append((log_id, stamp, employee, request,
                          approval, delivery, reason))
 
        # 3. Work out which rows belong on the current page
        total_pages = max(1, -(-len(shown) // PAGE_SIZE))      # round up
        self.page = min(self.page, total_pages - 1)
        start = self.page * PAGE_SIZE
        page_rows = shown[start:start + PAGE_SIZE]
 
        # 4. Fill the table (row colour comes from Delivery, else Approval)
        self.tree.delete(*self.tree.get_children())
        for row in page_rows:
            approval, delivery = row[4], row[5]
            tag = delivery if delivery in ROW_COLORS else approval
            self.tree.insert("", "end", values=row, tags=(tag,))
 
        # 5. Update labels and buttons
        self.count_label.configure(text=f"{len(shown)} entries")
        self.page_label.configure(text=f"Page {self.page + 1} of {total_pages}")
        self.prev_button.configure(state="normal" if self.page > 0 else "disabled")
        self.next_button.configure(
            state="normal" if self.page < total_pages - 1 else "disabled")
 
    def apply_filters(self):
        """Go back to page 1 and reload (used by search and filter)."""
        self.page = 0
        self.load()
 
    def next_page(self):
        self.page += 1
        self.load()
 
    def prev_page(self):
        self.page -= 1
        self.load()
 