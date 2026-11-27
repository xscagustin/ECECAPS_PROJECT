"""
inventory_terminal.py
---------------------
"Inventory Terminal" page for the Hospital IAM Sorting Hub (Courier / Admin).
Tab 1: Requests & QR  (see Chapter 4, sections 4.1.3, 4.1.6 and 4.2.1)

What the courier does here:
    1. Picks an approved request from the table on the left.
    2. Checks / corrects the SKU, quantity and compartment on the right.
    3. Presses "Generate QR". The page then:
         - signs the QR fields with the HMAC key (same key Package Receive uses)
         - saves a row in the new QrCodes table
         - takes the quantity out of Inventory
         - sets the request's state to "Ready"  (Package Receive only accepts "Ready")
         - shows the QR image and saves it as a PNG you can print
    4. Can also put a request On Hold, or release it back to Pending.

How app.py uses this file (same pattern as the other pages):
    InventoryTerminalPage(parent, cursor, user)

Libraries:
    pip install customtkinter pillow qrcode mysql-connector-python

Database assumptions (matches your screenshots):
    Requests  : request_id, item_name, quantity, date, time, courier_id,
                requester_id, state, Department, Approval
    Inventory : item_name, sku_id, quantity, date, time, package_id
    QrCodes   : created automatically below if it does not exist yet
"""

import json
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import ttk, W

import customtkinter as ctk
import qrcode

# Reuse the signing function (and secret key) from Package Receive so both
# pages always agree on how a QR is signed.
from package_receive import sign_fields

# =============================================================================
# CONFIG - things you are likely to change
# =============================================================================
COLORS = {
    "primary": "#0f766e",
    "warning": "#b45309",
    "side_bg": "#f3f6f8",
    "error": "#b91c1c",
    "success": "#15803d",
}

# Row colours in the requests table
STATE_COLORS = {
    "Pending": "#e0f2fe",
    "On Hold": "#fef3c7",
    "Ready": "#dcfce7",
}

# States shown in the table (only requests that are already Approved)
SHOWN_STATES = ("Pending", "On Hold", "Ready")

# The Requests table has no sensitivity column, so it is worked out from the
# SKU. Any SKU starting with one of these counts as "Sensitive".
SENSITIVE_PREFIXES = ("CTL-", "BLD-", "MED-INS", "MED-EPI", "MED-HEP")

# Folder where the QR label PNG files are saved
QR_FOLDER = Path("qr_labels")

# Created automatically the first time the page opens
CREATE_QR_TABLE = """
CREATE TABLE IF NOT EXISTS QrCodes (
    qr_id          INT AUTO_INCREMENT PRIMARY KEY,
    request_id     INT NOT NULL,
    sku_id         VARCHAR(30) NOT NULL,
    quantity       INT NOT NULL,
    compartment_id VARCHAR(20) NOT NULL,
    description    VARCHAR(255),
    destination    VARCHAR(50) NOT NULL,
    sensitivity    VARCHAR(20) NOT NULL,
    tag            VARCHAR(64) NOT NULL,      -- HMAC-SHA-256 (hex)
    qr_text        TEXT NOT NULL,             -- exact text encoded in the QR
    created_by     VARCHAR(20) NOT NULL,      -- courier employee ID
    created_at     DATETIME NOT NULL,
    status         VARCHAR(20) DEFAULT 'Active'   -- Active / Claimed / Void
)
"""

# Table columns: (database column, heading, width in pixels)
TABLE_COLUMNS = [
    ("request_id", "Request", 70),
    ("item_name",  "Item Name", 200),
    ("quantity",   "Qty", 50),
    ("Department", "Destination", 100),
    ("requester_id", "Requester", 80),
    ("state",      "State", 80),
]


# =============================================================================
# The page
# =============================================================================
class InventoryTerminalPage(ctk.CTkFrame):
    def __init__(self, parent, cursor, user):
        super().__init__(parent, fg_color="transparent")
        self.cursor = cursor
        self.user = user
        self.selected = None        # dict describing the selected request
        self.qr_image = None        # keeps a reference so Tk doesn't discard it
        self.qr_path = None         # PNG file of the last QR shown

        self.cursor.execute(CREATE_QR_TABLE)

        # Page title
        ctk.CTkLabel(self, text="Inventory Terminal", anchor="w",
                     font=ctk.CTkFont(size=22, weight="bold")
                     ).pack(fill="x", padx=10, pady=(4, 0))
        ctk.CTkLabel(self, text="Review approved requests, confirm the "
                                "contents, then generate the signed QR label.",
                     anchor="w", text_color="gray40").pack(fill="x", padx=10)

        # Tabs inside this page. Only the first one is built for now;
        # add more with self.tabs.add("...") later.
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.build_requests_tab(self.tabs.add("Requests & QR"))

        self.load_requests()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def build_requests_tab(self, tab):
        """Left: approved requests table.  Right: confirm form + QR preview."""
        # ---- left: table ----
        left = ctk.CTkFrame(tab, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        bar = ctk.CTkFrame(left, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(bar, text="Approved requests",
                     font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(bar, text="Refresh queue", width=110,
                      fg_color=COLORS["primary"],
                      command=self.load_requests).pack(side="right")

        ids = [c[0] for c in TABLE_COLUMNS]
        self.tree = ttk.Treeview(left, columns=ids, show="headings")
        for col_id, title, width in TABLE_COLUMNS:
            self.tree.heading(col_id, text=title, anchor=W)
            self.tree.column(col_id, width=width, anchor=W, stretch=True)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_selected)
        for state, color in STATE_COLORS.items():
            self.tree.tag_configure(state, background=color)

        # ---- right: confirm form ----
        form = ctk.CTkScrollableFrame(tab, width=300, fg_color=COLORS["side_bg"])
        form.pack(side="right", fill="y")

        ctk.CTkLabel(form, text="Confirm inventory record", anchor="w",
                     font=ctk.CTkFont(size=16, weight="bold")
                     ).pack(fill="x", padx=8, pady=(8, 2))

        # Read-only summary of the selected request
        self.summary = ctk.CTkLabel(form, text="Select a request.", anchor="w",
                                    justify="left", wraplength=260)
        self.summary.pack(fill="x", padx=8, pady=(0, 6))

        # Editable fields the courier confirms: label -> entry
        self.entries = {}
        for label in ("SKU ID", "Quantity", "Compartment", "Description"):
            ctk.CTkLabel(form, text=label, anchor="w").pack(fill="x", padx=8)
            entry = ctk.CTkEntry(form)
            entry.pack(fill="x", padx=8, pady=(0, 6))
            self.entries[label] = entry

        # Buttons
        self.generate_button = ctk.CTkButton(
            form, text="Confirm & generate QR", fg_color=COLORS["primary"],
            command=self.generate_qr)
        self.generate_button.pack(fill="x", padx=8, pady=(6, 4))

        buttons = ctk.CTkFrame(form, fg_color="transparent")
        buttons.pack(fill="x", padx=8)
        ctk.CTkButton(buttons, text="Put on hold", width=110,
                      fg_color=COLORS["warning"],
                      command=lambda: self.change_state("Pending", "On Hold")
                      ).pack(side="left", expand=True, padx=(0, 4))
        ctk.CTkButton(buttons, text="Release hold", width=110,
                      fg_color="gray40",
                      command=lambda: self.change_state("On Hold", "Pending")
                      ).pack(side="left", expand=True, padx=(4, 0))

        self.status = ctk.CTkLabel(form, text="", wraplength=260,
                                   justify="left", anchor="w")
        self.status.pack(fill="x", padx=8, pady=6)

        # QR preview
        self.qr_label = ctk.CTkLabel(form, text="QR label appears here",
                                     width=200, height=200, fg_color="white",
                                     text_color="gray40")
        self.qr_label.pack(pady=4)
        ctk.CTkButton(form, text="Open QR image to print", fg_color="gray40",
                      command=self.open_qr).pack(fill="x", padx=8, pady=(4, 8))

    # ------------------------------------------------------------------
    # Loading data
    # ------------------------------------------------------------------
    def load_requests(self):
        """Fill the table with approved requests that are not yet delivered."""
        column_list = ", ".join(f"`{c[0]}`" for c in TABLE_COLUMNS)
        marks = ", ".join(["%s"] * len(SHOWN_STATES))
        self.cursor.execute(
            f"SELECT {column_list} FROM Requests "
            f"WHERE Approval = 'Approved' AND state IN ({marks}) "
            f"ORDER BY request_id", SHOWN_STATES)

        self.tree.delete(*self.tree.get_children())
        for row in self.cursor.fetchall():
            self.tree.insert("", "end", values=row, tags=(str(row[-1]),))

    def on_row_selected(self, event):
        """Load the clicked request into the form (and its QR if it has one)."""
        picked = self.tree.selection()
        if not picked:
            return
        request_id = self.tree.item(picked[0])["values"][0]

        self.cursor.execute(
            "SELECT item_name, quantity, Department, state FROM Requests "
            "WHERE request_id = %s", (request_id,))
        item_name, quantity, destination, state = self.cursor.fetchone()

        # Look up the SKU and stock level from the Inventory table
        self.cursor.execute(
            "SELECT sku_id, quantity FROM Inventory WHERE item_name = %s",
            (item_name,))
        found = self.cursor.fetchone()
        sku, stock = found if found else ("", 0)

        self.selected = {"request_id": request_id, "item_name": item_name,
                         "destination": destination, "state": state}

        self.summary.configure(
            text=f"REQ-{request_id} · {state}\n{item_name}\n"
                 f"Destination: {destination}\nIn stock: {stock}")
        self.set_entries({"SKU ID": sku, "Quantity": quantity,
                          "Compartment": "", "Description": item_name})
        self.show_status("", False)

        # Already has a QR? Show it again instead of making a second one.
        if state == "Ready":
            self.cursor.execute(
                "SELECT qr_text, compartment_id FROM QrCodes "
                "WHERE request_id = %s AND status = 'Active' "
                "ORDER BY qr_id DESC LIMIT 1", (request_id,))
            saved = self.cursor.fetchone()
            if saved:
                self.entries["Compartment"].delete(0, "end")
                self.entries["Compartment"].insert(0, saved[1])
                self.show_qr(saved[0], request_id)
        self.generate_button.configure(
            state="normal" if state == "Pending" else "disabled")

    # ------------------------------------------------------------------
    # Generate the QR (the main job of this page)
    # ------------------------------------------------------------------
    def generate_qr(self):
        """Validate the form, save the QR, update Inventory and Requests."""
        if not self.selected:
            return self.show_status("Select a request first.", True)

        # 1. Read and check what the courier confirmed
        sku = self.entries["SKU ID"].get().strip()
        compartment = self.entries["Compartment"].get().strip()
        description = self.entries["Description"].get().strip()
        try:
            quantity = int(self.entries["Quantity"].get())
            if quantity <= 0:
                raise ValueError
        except ValueError:
            return self.show_status("Quantity must be a positive number.", True)
        if not sku or not compartment:
            return self.show_status("SKU ID and Compartment are required.", True)

        # 2. Make sure the SKU exists and there is enough stock
        self.cursor.execute("SELECT quantity FROM Inventory WHERE sku_id = %s", (sku,))
        row = self.cursor.fetchone()
        if row is None:
            return self.show_status(f"SKU {sku} is not in the inventory.", True)
        if row[0] < quantity:
            return self.show_status(f"Only {row[0]} in stock.", True)

        # 3. Build the signed QR text. The field names must match what
        #    package_receive.py reads: request_id, sku_id, quantity,
        #    compartment_id, description, destination, sensitivity, tag.
        request_id = self.selected["request_id"]
        sensitivity = "Sensitive" if sku.startswith(SENSITIVE_PREFIXES) else "Routine"
        fields = {"request_id": request_id, "sku_id": sku, "quantity": quantity,
                  "compartment_id": compartment, "description": description,
                  "destination": self.selected["destination"],
                  "sensitivity": sensitivity}
        tag = sign_fields(fields)
        qr_text = json.dumps({**fields, "tag": tag})

        # 4. Save everything. (autocommit is on, so each line is saved at once)
        try:
            self.cursor.execute(
                "INSERT INTO QrCodes (request_id, sku_id, quantity, compartment_id, "
                "description, destination, sensitivity, tag, qr_text, created_by, "
                "created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (request_id, sku, quantity, compartment, description,
                 fields["destination"], sensitivity, tag, qr_text,
                 self.user["id"], datetime.now()))
            self.cursor.execute(
                "UPDATE Inventory SET quantity = quantity - %s WHERE sku_id = %s",
                (quantity, sku))
            self.cursor.execute(
                "UPDATE Requests SET quantity = %s, courier_id = %s, state = 'Ready' "
                "WHERE request_id = %s", (quantity, self.user["id"], request_id))
        except Exception as error:
            return self.show_status(f"Could not save: {error}", True)

        # 5. Show the result
        self.show_qr(qr_text, request_id)
        self.selected["state"] = "Ready"
        self.generate_button.configure(state="disabled")
        self.show_status(f"QR created. REQ-{request_id} is now Ready ({sensitivity}).",
                         False)
        self.load_requests()

    def change_state(self, from_state, to_state):
        """Move the selected request between Pending and On Hold."""
        if not self.selected:
            return self.show_status("Select a request first.", True)
        if self.selected["state"] != from_state:
            return self.show_status(f"Only {from_state} requests can be changed "
                                    f"to {to_state}.", True)
        self.cursor.execute("UPDATE Requests SET state = %s WHERE request_id = %s",
                            (to_state, self.selected["request_id"]))
        self.selected["state"] = to_state
        self.generate_button.configure(
            state="normal" if to_state == "Pending" else "disabled")
        self.show_status(f"Request set to {to_state}.", False)
        self.load_requests()

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------
    def show_qr(self, qr_text, request_id):
        """Draw the QR on screen and save it as a PNG for printing."""
        image = qrcode.make(qr_text).get_image()      # a Pillow image
        QR_FOLDER.mkdir(exist_ok=True)
        self.qr_path = QR_FOLDER / f"REQ-{request_id}.png"
        image.save(self.qr_path)

        self.qr_image = ctk.CTkImage(image, size=(200, 200))
        self.qr_label.configure(image=self.qr_image, text="")

    def open_qr(self):
        """Open the saved PNG in the default image viewer (print from there)."""
        if self.qr_path:
            webbrowser.open(self.qr_path.resolve().as_uri())
        else:
            self.show_status("No QR to open yet.", True)

    def set_entries(self, values):
        """Replace the text of the form entries. values: label -> text."""
        for label, text in values.items():
            self.entries[label].delete(0, "end")
            self.entries[label].insert(0, str(text))

    def show_status(self, message, error):
        color = COLORS["error"] if error else COLORS["success"]
        self.status.configure(text=message, text_color=color)
