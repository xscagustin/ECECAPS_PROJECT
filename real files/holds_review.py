"""
holds_review.py
---------------
"Holds & Review" page for the Hospital IAM Sorting Hub.
 
Tab 1 (this file): Approval Queue
    The Department Head / Admin sees every request that is waiting for a
    decision, selects one, and presses Approve or Disapprove.
      - Approve    -> Approval becomes "Approved" and state becomes "Pending"
                      (the Inventory Terminal page only picks up approved
                      requests)
      - Disapprove -> Approval becomes "Rejected" and state becomes "Denied"
                      (a reason is required)
    Every decision is written to the AuditLog table (Chapter 4.1.6).
 
Tab 2 (later): Admin override. Add it in build_override_tab() below.
 
How app.py uses this file:
    HoldsReviewPage(parent, cursor, user)
      parent : the tab this page is placed in
      cursor : the shared MySQL cursor created by app.py (autocommit is on)
      user   : dict with "id", "name", "role" and "department"
 
Assumptions about the database (change the CONFIG below to match yours):
    Requests : request_id, item_name, quantity, date, time, courier_id,
               requester_id, state, Department, Approval
    AuditLog : timestamp, employee_id, request_id, decision, reason
"""
 
from datetime import datetime
from tkinter import ttk, W
import customtkinter as ctk
import mysql.connector
 
# =============================================================================
# CONFIG - edit this section to match your database and look
# =============================================================================
 
COLORS = {
    "primary": "#0f766e",
    "danger": "#b91c1c",
    "card_bg": "#ffffff",
    "side_bg": "#f3f6f8",
    "success": "#15803d",
}
 
# The approval decision is stored in its own column of the Requests table,
# separate from the delivery "state" column.
APPROVAL_COLUMN = "Approval"
PENDING_STATE = "Pending Approval"   # waiting for a decision (shown in this tab)
APPROVED_STATE = "Approved"          # what the Inventory Terminal page looks for
DISAPPROVED_STATE = "Rejected"
DENIED_REQUEST_STATE = "Denied"      # delivery state given to rejected requests
PENDING_REQUEST_STATE = "Pending"    # delivery state given to approved requests
 
# Only these access levels may make a decision
ALLOWED_ROLES = ("Departmental", "Administrative")
 
# Column in the Requests table that identifies a request
ID_COLUMN = "request_id"
 
# Queue table columns: (database column, heading text, width in pixels)
QUEUE_COLUMNS = [
    ("request_id",   "Request ID", 90),
    ("item_name",    "Item",       200),
    ("quantity",     "Qty",         50),
    ("Department",   "Department", 110),
    ("date",         "Date",        90),
    ("time",         "Time",        80),
    ("requester_id", "Requester",   90),
]
 
 
# =============================================================================
# The page
# =============================================================================
class HoldsReviewPage(ctk.CTkFrame):
    def __init__(self, parent, cursor, user):
        super().__init__(parent, fg_color="transparent")
        self.cursor = cursor
        self.user = user
        self.selected = None          # dict of the row currently selected
 
        # Page title
        ctk.CTkLabel(self, text="Holds & Review", anchor="w",
                     font=ctk.CTkFont(size=22, weight="bold")
                     ).pack(fill="x", padx=10, pady=(4, 0))
        self.count_label = ctk.CTkLabel(self, text="", anchor="w",
                                        text_color="gray40")
        self.count_label.pack(fill="x", padx=10)
 
        # Tabs inside this page (only the first one exists for now)
        self.tabs = ctk.CTkTabview(self, fg_color=COLORS["card_bg"])
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.build_queue_tab(self.tabs.add("Approval Queue"))
        # self.build_override_tab(self.tabs.add("Admin Override"))   # tab 2, later
 
        self.load_queue()
 
    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def build_queue_tab(self, tab):
        """Queue table on the left, decision panel on the right."""
        # --- left: table of pending requests ---
        left = ctk.CTkFrame(tab, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
 
        ids = [c[0] for c in QUEUE_COLUMNS]
        self.tree = ttk.Treeview(left, columns=ids, show="headings",
                                 selectmode="browse")
        for col_id, title, width in QUEUE_COLUMNS:
            self.tree.heading(col_id, text=title, anchor=W)
            self.tree.column(col_id, width=width, anchor=W)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.row_clicked)
 
        ctk.CTkButton(left, text="Refresh queue", width=120,
                      fg_color=COLORS["primary"], command=self.load_queue
                      ).pack(anchor="e", pady=8)
 
        # --- right: decision panel ---
        panel = ctk.CTkFrame(tab, width=280, fg_color=COLORS["side_bg"])
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)
 
        ctk.CTkLabel(panel, text="Approval decision",
                     font=ctk.CTkFont(size=16, weight="bold")
                     ).pack(anchor="w", padx=12, pady=(12, 4))
 
        self.details_label = ctk.CTkLabel(
            panel, text="Select a request from the queue.", anchor="nw",
            justify="left", wraplength=250)
        self.details_label.pack(fill="x", padx=12, pady=6)
 
        ctk.CTkLabel(panel, text="Reason (required to disapprove)", anchor="w"
                     ).pack(fill="x", padx=12, pady=(10, 0))
        self.reason_entry = ctk.CTkEntry(panel)
        self.reason_entry.pack(fill="x", padx=12)
 
        self.approve_button = ctk.CTkButton(
            panel, text="Approve request", fg_color=COLORS["primary"],
            command=lambda: self.decide(APPROVED_STATE))
        self.approve_button.pack(fill="x", padx=12, pady=(16, 6))
 
        self.disapprove_button = ctk.CTkButton(
            panel, text="Disapprove request", fg_color=COLORS["danger"],
            command=lambda: self.decide(DISAPPROVED_STATE))
        self.disapprove_button.pack(fill="x", padx=12)
 
        self.status_label = ctk.CTkLabel(panel, text="", wraplength=250,
                                         justify="left")
        self.status_label.pack(fill="x", padx=12, pady=10)
 
        # Users without approval rights can look but not decide
        if self.user["role"] not in ALLOWED_ROLES:
            self.approve_button.configure(state="disabled")
            self.disapprove_button.configure(state="disabled")
            self.show_status("Your access level cannot approve requests.", error=True)
 
    # ------------------------------------------------------------------
    # Loading data
    # ------------------------------------------------------------------
    def load_queue(self):
        """Fetch all pending requests and show them in the table."""
        columns = ", ".join(f"`{c[0]}`" for c in QUEUE_COLUMNS)
        self.cursor.execute(
            f"SELECT {columns} FROM Requests WHERE `{APPROVAL_COLUMN}` = %s "
            f"ORDER BY `date`, `time`", (PENDING_STATE,))
        rows = self.cursor.fetchall()
 
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert("", "end", values=row)
 
        self.count_label.configure(text=f"{len(rows)} requests pending")
        self.clear_selection()
 
    def row_clicked(self, event):
        """Remember the clicked row and show its details in the panel."""
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0])["values"]
        # pair each column name with its value, e.g. {"request_id": "REQ-1052", ...}
        self.selected = dict(zip([c[0] for c in QUEUE_COLUMNS], values))
 
        # Build the details text from the same column list as the table
        lines = [f"{title}: {self.selected[col]}" for col, title, _ in QUEUE_COLUMNS]
        self.details_label.configure(text="\n".join(lines))
        self.status_label.configure(text="")
 
    def clear_selection(self):
        self.selected = None
        self.details_label.configure(text="Select a request from the queue.")
        self.reason_entry.delete(0, "end")
 
    # ------------------------------------------------------------------
    # Approve / disapprove
    # ------------------------------------------------------------------
    def decide(self, new_state):
        """Save the decision for the selected request and log it."""
        # 1. Checks
        if self.selected is None:
            return self.show_status("Select a request first.", error=True)
        reason = self.reason_entry.get().strip()
        if new_state == DISAPPROVED_STATE and not reason:
            return self.show_status("Enter a reason to disapprove.", error=True)
 
        request_id = self.selected[ID_COLUMN]
 
        try:
            # 2. Update only if the request is STILL pending, so two approvers
            #    cannot decide the same request twice.
            if new_state == DISAPPROVED_STATE:
                # Rejected requests are also marked "Denied" in the state column
                self.cursor.execute(
                    f"UPDATE Requests SET `{APPROVAL_COLUMN}` = %s, state = %s "
                    f"WHERE `{ID_COLUMN}` = %s AND `{APPROVAL_COLUMN}` = %s",
                    (new_state, DENIED_REQUEST_STATE, request_id, PENDING_STATE))
            else:
                # Approved requests are marked "Pending" in the state column
                self.cursor.execute(
                    f"UPDATE Requests SET `{APPROVAL_COLUMN}` = %s, state = %s "
                    f"WHERE `{ID_COLUMN}` = %s AND `{APPROVAL_COLUMN}` = %s",
                    (new_state, PENDING_REQUEST_STATE, request_id, PENDING_STATE))
            if self.cursor.rowcount == 0:
                self.load_queue()
                return self.show_status(
                    f"{request_id} was already decided by someone else.", error=True)
 
            # 3. Audit log entry
            decision = "Approval" if new_state == APPROVED_STATE else "Disapproval"
            self.cursor.execute(
                "INSERT INTO AuditLog (timestamp, employee_id, request_id, "
                "decision, reason) VALUES (%s, %s, %s, %s, %s)",
                (datetime.now(), self.user["id"], request_id,
                 decision, reason or "Approved by " + self.user["role"]))
        except mysql.connector.Error as err:
            return self.show_status(f"Database error: {err}", error=True)
 
        # 4. Refresh the queue and tell the user
        self.load_queue()
        self.show_status(f"{request_id} {new_state.lower()}.", error=False)
 
    def show_status(self, message, error):
        color = COLORS["danger"] if error else COLORS["success"]
        self.status_label.configure(text=message, text_color=color)
 