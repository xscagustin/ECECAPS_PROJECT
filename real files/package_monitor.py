"""
Package Monitor page (a frame that app.py places inside its main window)

Tabs inside this page:
  1. In-Progress Deliveries : Requests table + "items on hold" card
  2. Available Inventory    : Inventory table + "Request inventory" form

How app.py uses this file:
    PackageMonitorPage(parent, cursor, user)
      parent : the frame/tab to place the page in
      cursor : the shared MySQL cursor created by app.py
      user   : dict with "id", "name" and "role" of the logged-in user

Everything you are likely to change (table columns, filters, form fields,
colours) lives in the CONFIG section below. The classes further down should
not need editing for ordinary changes.
"""

from datetime import datetime
from tkinter import ttk, W
import customtkinter as ctk
import mysql.connector

# =============================================================================
# CONFIG - edit this section to change the look, tables or form
# =============================================================================

# --- Colours ---
COLORS = {
    "primary": "#0f766e",     # buttons
    "card_bg": "#ffffff",
    "side_bg": "#f3f6f8",     # side cards and form background
    "error": "#b91c1c",
    "success": "#15803d",
}

# Row colour per state value (used by any table that has a state column)
STATE_COLORS = {
    "Delivered": "#dcfce7",   # green
    "On Hold": "#fef3c7",     # amber
    "Pending": "#e0f2fe",     # blue
}

# --- Table 1: in-progress deliveries (Requests table) ---
# "columns" = (database column, heading text, width in pixels)
# The columns are shown in this order. Add/remove rows to change the table.
REQUESTS_TABLE = {
    "table": "Requests",
    "columns": [
        ("item_name",    "Item Name",    200),
        ("quantity",     "Qty",           60),
        ("date",         "Date",          95),
        ("time",         "Time",          85),
        ("courier_id",   "Courier",       80),
        ("requester_id", "Requester",     90),
        ("state",        "State",         90),
    ],
    "search_column": "item_name",          # column the search box looks in
    "search_hint": "Search item name",
    "filter_column": "state",              # column the dropdown filters on
    "filter_options": ["All states", "Pending", "On Hold", "Delivered"],  # 1st = "no filter"
    "state_column": "state",               # column used for row colours (or None)
    "page_size": 10,
}

# --- Table 2: available inventory (Inventory table) ---
INVENTORY_TABLE = {
    "table": "Inventory",
    "columns": [
        ("item_name",  "Item Name",   200),
        ("sku_id",     "SKU ID",      110),
        ("quantity",   "Available",    70),
        ("date",       "Date",         95),
        ("time",       "Time",         85),
        ("package_id", "Package ID",   90),
    ],
    "search_column": "item_name",
    "search_hint": "Search item name",
    "filter_column": None,                 # None = no dropdown filter
    "filter_options": [],
    "state_column": None,
    "page_size": 10,
}

# --- "Items on hold" card on tab 1 ---
HOLD_STATE = "On Hold"          # State value that counts as a hold
PENDING_STATE = "Pending"       # State value that counts as pending
DELIVERED_STATE = "Delivered"   # State value that counts as delivered

# --- "Request inventory" form on tab 2 ---
DEPARTMENTS = ["Pharmacy", "Emergency", "Theatre", "Ward 3", "Laboratory",
               "Radiology", "Records"]
NEW_REQUEST_STATE = "Pending"   # State given to every new request
APPROVAL_NOTE = "Sensitive items require Department Head or Admin approval."

# Each field: label, column (Requests column it is saved to; None = not saved),
#             kind ("item" = dropdown of inventory items, "entry" = text box,
#                   "fixed" = read-only text, "combo" = dropdown of "values"),
#             default / values (optional)
# In a "default", {user_id} is replaced by the logged-in user's ID.
FORM_FIELDS = [
    {"label": "Item",        "column": "item_name",    "kind": "item"},
    {"label": "Quantity",    "column": "quantity",     "kind": "entry", "default": "1"},
    {"label": "Requester",   "column": "requester_id", "kind": "fixed",
     "default": "{user_id}"},
    # Destination is in the design but the Requests table has no column for it
    # yet. Set "column" to the real column name once you add one.
    {"label": "Destination", "column": None,           "kind": "combo",
     "values": DEPARTMENTS},
]

# Which Inventory column holds the item names shown in the form's item dropdown
INVENTORY_NAME_COLUMN = "item_name"


# =============================================================================
# Reusable table: search box + filter dropdown + table + page buttons
# =============================================================================
class DataTable(ctk.CTkFrame):
    """A paged, searchable table that is described entirely by a config dict
    (see REQUESTS_TABLE / INVENTORY_TABLE above)."""

    def __init__(self, master, config, cursor, on_select=None):
        super().__init__(master, fg_color="transparent")
        self.cfg = config
        self.cursor = cursor                # shared MySQL cursor from app.py
        self.on_select = on_select          # called with the clicked row (a list)
        self.page = 0
        self.page_size = config["page_size"]

        # --- top bar: search, filter, count ---
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", pady=(0, 8))

        self.search_entry = ctk.CTkEntry(top, width=220,
                                         placeholder_text=config["search_hint"])
        self.search_entry.pack(side="left", padx=(0, 8))
        self.search_entry.bind("<Return>", lambda e: self.apply_filters())

        self.filter_box = None
        if config["filter_column"]:
            self.filter_box = ctk.CTkComboBox(
                top, values=config["filter_options"], width=140,
                state="readonly", command=lambda v: self.apply_filters())
            self.filter_box.set(config["filter_options"][0])
            self.filter_box.pack(side="left", padx=(0, 8))

        ctk.CTkButton(top, text="Search", width=80, fg_color=COLORS["primary"],
                      command=self.apply_filters).pack(side="left")

        self.count_label = ctk.CTkLabel(top, text="")
        self.count_label.pack(side="right")

        # --- the table itself ---
        ids = [c[0] for c in config["columns"]]
        self.tree = ttk.Treeview(self, columns=ids, show="headings",
                                 height=self.page_size)
        for col_id, title, width in config["columns"]:
            self.tree.heading(col_id, text=title, anchor=W)
            self.tree.column(col_id, width=width, anchor=W, stretch=True)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._row_clicked)

        for state, color in STATE_COLORS.items():     # row colours
            self.tree.tag_configure(state, background=color)

        # --- bottom bar: prev / page label / next ---
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(pady=8)
        self.prev_button = ctk.CTkButton(bottom, text="Prev", width=80,
                                         fg_color=COLORS["primary"],
                                         command=self.prev_page)
        self.prev_button.pack(side="left", padx=8)
        self.page_label = ctk.CTkLabel(bottom, text="Page 1 of 1")
        self.page_label.pack(side="left", padx=8)
        self.next_button = ctk.CTkButton(bottom, text="Next", width=80,
                                         fg_color=COLORS["primary"],
                                         command=self.next_page)
        self.next_button.pack(side="left", padx=8)

        self.load()

    def _where(self):
        """Build the WHERE clause from the search box and the filter dropdown.
        Returns (sql_text, parameters)."""
        conditions, params = [], []

        text = self.search_entry.get().strip()
        if text:
            conditions.append(f"`{self.cfg['search_column']}` LIKE %s")
            params.append(f"%{text}%")

        if self.filter_box and self.filter_box.get() != self.cfg["filter_options"][0]:
            conditions.append(f"`{self.cfg['filter_column']}` = %s")
            params.append(self.filter_box.get())

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        return where, params

    def load(self):
        """Fetch the current page from the database and show it."""
        table = self.cfg["table"]
        where, params = self._where()
        column_list = ", ".join(f"`{c[0]}`" for c in self.cfg["columns"])

        # total rows -> number of pages
        self.cursor.execute(f"SELECT COUNT(*) FROM `{table}`{where}", params)
        total_rows = self.cursor.fetchone()[0]
        total_pages = max(1, -(-total_rows // self.page_size))   # round up
        self.page = min(self.page, total_pages - 1)

        # rows for this page
        self.cursor.execute(
            f"SELECT {column_list} FROM `{table}`{where} LIMIT %s OFFSET %s",
            params + [self.page_size, self.page * self.page_size])
        rows = self.cursor.fetchall()

        # find which column (if any) decides the row colour
        ids = [c[0] for c in self.cfg["columns"]]
        state_index = ids.index(self.cfg["state_column"]) if self.cfg["state_column"] else None

        self.tree.delete(*self.tree.get_children())
        for row in rows:
            tag = (str(row[state_index]),) if state_index is not None else ()
            self.tree.insert("", "end", values=row, tags=tag)

        self.count_label.configure(text=f"{total_rows} records")
        self.page_label.configure(text=f"Page {self.page + 1} of {total_pages}")
        self.prev_button.configure(state="normal" if self.page > 0 else "disabled")
        self.next_button.configure(
            state="normal" if self.page < total_pages - 1 else "disabled")

    def apply_filters(self):
        self.page = 0
        self.load()

    def next_page(self):
        self.page += 1
        self.load()

    def prev_page(self):
        self.page -= 1
        self.load()

    def _row_clicked(self, event):
        selection = self.tree.selection()
        if selection and self.on_select:
            self.on_select(self.tree.item(selection[0])["values"])


# =============================================================================
# The page itself
# =============================================================================
class PackageMonitorPage(ctk.CTkFrame):
    def __init__(self, master, cursor, user):
        super().__init__(master, fg_color="transparent")
        self.cursor = cursor
        self.user = user

        # Page title
        ctk.CTkLabel(self, text="Package Monitor", anchor="w",
                     font=ctk.CTkFont(size=22, weight="bold")
                     ).pack(fill="x", padx=10, pady=(4, 0))
        ctk.CTkLabel(self, text=f"In progress deliveries · "
                                f"{self.user['role']} view", anchor="w",
                     text_color="gray40").pack(fill="x", padx=10)

        # Tabs inside this page
        self.tabs = ctk.CTkTabview(self, fg_color=COLORS["card_bg"])
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.build_deliveries_tab(self.tabs.add("In-Progress Deliveries"))
        self.build_inventory_tab(self.tabs.add("Available Inventory"))

        self.refresh_holds()

    # ----------------------------------------------------------- tab 1 -----
    def build_deliveries_tab(self, tab):
        """Requests table on the left, 'items on hold' card on the right."""
        self.deliveries = DataTable(tab, REQUESTS_TABLE, self.cursor)
        self.deliveries.pack(side="left", fill="both", expand=True, padx=(0, 12))

        card = ctk.CTkFrame(tab, width=230, fg_color=COLORS["side_bg"])
        card.pack(side="right", fill="y")
        card.pack_propagate(False)

        self.summary_label = ctk.CTkLabel(card, text="", anchor="w",
                                          justify="left")
        self.summary_label.pack(fill="x", padx=12, pady=(12, 8))

        ctk.CTkLabel(card, text="Items on hold", anchor="w",
                     font=ctk.CTkFont(weight="bold")
                     ).pack(fill="x", padx=12)
        self.hold_label = ctk.CTkLabel(card, text="", anchor="nw",
                                       justify="left", wraplength=200)
        self.hold_label.pack(fill="x", padx=12, pady=6)

    def refresh_holds(self):
        """Update the summary counts and the list of held requests."""
        table = REQUESTS_TABLE["table"]
        self.cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
        total = self.cursor.fetchone()[0]

        # count of requests in each state we care about
        counts = {}
        for state in (PENDING_STATE, HOLD_STATE, DELIVERED_STATE):
            self.cursor.execute(
                f"SELECT COUNT(*) FROM `{table}` WHERE state = %s", (state,))
            counts[state] = self.cursor.fetchone()[0]

        # first few held requests for the list
        self.cursor.execute(f"SELECT item_name, quantity FROM `{table}` "
                            f"WHERE state = %s LIMIT 8", (HOLD_STATE,))
        held = self.cursor.fetchall()

        self.summary_label.configure(
            text=f"{total} requests\n"
                 f"{counts[PENDING_STATE]} pending · "
                 f"{counts[HOLD_STATE]} on hold · "
                 f"{counts[DELIVERED_STATE]} delivered")
        self.hold_label.configure(
            text="\n".join(f"• {name} (x{qty})" for name, qty in held)
            or "None")

    # ----------------------------------------------------------- tab 2 -----
    def build_inventory_tab(self, tab):
        """Inventory table on the left, request form on the right.
        Clicking an inventory row fills in the form's item."""
        self.inventory = DataTable(tab, INVENTORY_TABLE, self.cursor,
                                   on_select=self.fill_form_item)
        self.inventory.pack(side="left", fill="both", expand=True, padx=(0, 12))

        self.build_request_form(tab)

    def build_request_form(self, parent):
        """Build the 'Request inventory' widget from FORM_FIELDS."""
        form = ctk.CTkFrame(parent, width=260, fg_color=COLORS["side_bg"])
        form.pack(side="right", fill="y")
        form.pack_propagate(False)

        ctk.CTkLabel(form, text="Request inventory",
                     font=ctk.CTkFont(size=16, weight="bold")
                     ).pack(anchor="w", padx=12, pady=(12, 4))

        self.form_widgets = {}    # label -> widget, used when submitting
        for field in FORM_FIELDS:
            ctk.CTkLabel(form, text=field["label"], anchor="w"
                         ).pack(fill="x", padx=12, pady=(8, 0))

            if field["kind"] == "item":
                widget = ctk.CTkComboBox(form, values=self.get_item_names(),
                                         state="readonly")
                widget.set("")
            elif field["kind"] == "combo":
                widget = ctk.CTkComboBox(form, values=field["values"],
                                         state="readonly")
                widget.set(field["values"][0])
            else:                                  # "entry" or "fixed"
                widget = ctk.CTkEntry(form)
                default = field.get("default", "").format(user_id=self.user["id"])
                widget.insert(0, default)
                if field["kind"] == "fixed":
                    widget.configure(state="disabled")

            widget.pack(fill="x", padx=12)
            self.form_widgets[field["label"]] = widget

        ctk.CTkLabel(form, text=APPROVAL_NOTE, wraplength=230, justify="left",
                     text_color="gray40").pack(fill="x", padx=12, pady=10)

        ctk.CTkButton(form, text="Submit request", fg_color=COLORS["primary"],
                      command=self.submit_request).pack(fill="x", padx=12)

        self.form_status = ctk.CTkLabel(form, text="", wraplength=230,
                                        justify="left")
        self.form_status.pack(fill="x", padx=12, pady=8)

    def get_item_names(self):
        """List of item names for the form's item dropdown."""
        self.cursor.execute(f"SELECT DISTINCT `{INVENTORY_NAME_COLUMN}` "
                            f"FROM `{INVENTORY_TABLE['table']}`")
        return [row[0] for row in self.cursor.fetchall()]

    def fill_form_item(self, row):
        """Called when an inventory row is clicked. Assumes the first table
        column is the item name (true for INVENTORY_TABLE above)."""
        for field in FORM_FIELDS:
            if field["kind"] == "item":
                self.form_widgets[field["label"]].set(str(row[0]))

    def submit_request(self):
        """Validate the form and insert a new row into the Requests table."""
        # 1. Collect the values from the form (only fields saved to a column)
        values = {}
        for field in FORM_FIELDS:
            if field["column"]:
                values[field["column"]] = self.form_widgets[field["label"]].get().strip()

        # 2. Basic checks
        if not values.get("item_name"):
            return self.show_status("Please choose an item.", error=True)
        try:
            values["quantity"] = int(values["quantity"])
            if values["quantity"] <= 0:
                raise ValueError
        except (KeyError, ValueError):
            return self.show_status("Quantity must be a positive number.", error=True)

        # 3. Fields the system fills in automatically
        now = datetime.now()
        values["date"] = now.strftime("%Y-%m-%d")
        values["time"] = now.strftime("%H:%M:%S")
        values["state"] = NEW_REQUEST_STATE

        # 4. Save it
        columns = ", ".join(f"`{c}`" for c in values)
        placeholders = ", ".join(["%s"] * len(values))
        try:
            self.cursor.execute(
                f"INSERT INTO `{REQUESTS_TABLE['table']}` ({columns}) "
                f"VALUES ({placeholders})", list(values.values()))
        except mysql.connector.Error as err:
            return self.show_status(f"Could not save: {err}", error=True)

        # 5. Refresh the first tab and tell the user
        self.deliveries.load()
        self.refresh_holds()
        self.show_status("Request submitted.", error=False)

    def show_status(self, message, error):
        color = COLORS["error"] if error else COLORS["success"]
        self.form_status.configure(text=message, text_color=color)
