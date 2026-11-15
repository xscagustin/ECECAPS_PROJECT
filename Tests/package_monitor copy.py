"""
Hospital IAM Sorting Hub - customtkinter app with MySQL (mysql.connector)

Boilerplate you can extend:
  * All SQL lives in the Database class.
  * Database calls run in background threads (PackageMonitorPage._background),
    so the window never freezes. Results come back on the UI thread.
  * Messages to the user go through PackageMonitorPage.set_status(...)
    (an in-app banner). No modal popups are used on purpose.
  * Places for your own logic are marked  # TODO
"""

import queue
import ssl
import threading
import time
import traceback
from datetime import datetime

# Compatibility shim for older mysql-connector versions on newer Python.
# You can delete this block after: pip install --upgrade mysql-connector-python
if not hasattr(ssl, "PROTOCOL_TLSv1"):
    ssl.PROTOCOL_TLSv1 = ssl.PROTOCOL_TLS
if not hasattr(ssl, "PROTOCOL_TLSv1_1"):
    ssl.PROTOCOL_TLSv1_1 = ssl.PROTOCOL_TLS
if not hasattr(ssl, "PROTOCOL_TLSv1_2"):
    ssl.PROTOCOL_TLSv1_2 = ssl.PROTOCOL_TLS

import faulthandler
import tkinter as tk

import customtkinter as ctk
import mysql.connector

ctk.set_appearance_mode("light")

# Edit these to match your MySQL server (pip install mysql-connector-python)
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "1212",
    "database": "HospitalDatabase",
    "connection_timeout": 3,  # seconds (only limits the initial connect)
}


# --------------------------------------------------------------------------- #
# Theme
# --------------------------------------------------------------------------- #
class Theme:
    BG = "#F5F5F5"
    CARD = "#FFFFFF"
    BORDER = "#E3E7E6"
    TEXT = "#1F2D2B"
    MUTED = "#6B7775"
    PRIMARY = "#3B7A72"
    PRIMARY_HOVER = "#2F655E"
    PRIMARY_SOFT = "#E3F0ED"
    TABLE_HEAD = "#F1F4F3"
    WARN_BG = "#FDF1DF"
    WARN_TEXT = "#8A5A12"
    WARN_SOFT = "#FBE6C4"
    ERROR_BG = "#FBE4E4"
    ERROR_TEXT = "#9B2C2C"

    FONT = "Segoe UI"

    @classmethod
    def font(cls, size=12, weight="normal"):
        return ctk.CTkFont(family=cls.FONT, size=size, weight=weight)

    @classmethod
    def tkfont(cls, size=12, weight="normal"):
        """Font tuple for plain tkinter widgets (used inside table rows, which must be light)."""
        return (cls.FONT, -size, weight)


# --------------------------------------------------------------------------- #
# Database layer (all SQL lives here, so the UI classes stay clean)
# --------------------------------------------------------------------------- #
class Database:
    """Thin wrapper around mysql.connector. Opens a short-lived connection per call."""

    # Stock-level filter options -> SQL condition
    LEVELS = {
        "Out of stock": "quantity = 0",
        "Low stock (1-9)": "quantity BETWEEN 1 AND 9",
        "In stock (10+)": "quantity >= 10",
    }
    KNOWN_STATES = ["Ready", "Held", "Pending"]

    def __init__(self, config):
        self.config = config

    def _run(self, sql, params=(), write=False):
        conn = mysql.connector.connect(**self.config)
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute(sql, params)
            if write:
                conn.commit()
                return cur.lastrowid
            return cur.fetchall()
        finally:
            conn.close()

    # ---- retrieval ----
    def fetch_requests(self, search="", state=None, courier=None):
        """
        Requests has no ID column, so a display ID (REQ-1001, REQ-1002, ...) is
        generated in Python from the date_time order. (No MySQL 8 features needed.)
        Newest requests come first. The SKU is looked up from Inventory by item name.
        """
        rows = self._run("""
            SELECT r.item_name,
                   (SELECT MIN(i.sku_id) FROM Inventory i
                     WHERE i.item_name = r.item_name) AS sku_id,
                   r.quantity, r.date_time, r.courier_id, r.requester_id, r.state
            FROM Requests r
            ORDER BY r.date_time ASC
        """)
        for number, row in enumerate(rows, start=1001):
            row["request_no"] = number

        search = search.lower()
        result = []
        for r in rows:
            if state and r["state"] != state:
                continue
            if courier and r["courier_id"] != courier:
                continue
            if search and search not in f"req-{r['request_no']}" \
                    and search not in (r["item_name"] or "").lower():
                continue
            result.append(r)
        result.reverse()
        return result

    def fetch_inventory(self, search="", item=None, level=None):
        sql = "SELECT item_name, sku_id, quantity, package_id FROM Inventory WHERE 1 = 1"
        params = []
        if search:
            sql += " AND (item_name LIKE %s OR sku_id LIKE %s)"
            params += [f"%{search}%", f"%{search}%"]
        if item:
            sql += " AND item_name = %s"
            params.append(item)
        if level in self.LEVELS:
            sql += f" AND {self.LEVELS[level]}"
        sql += " ORDER BY item_name"
        return self._run(sql, params)

    def fetch_filter_options(self):
        """Distinct values used to fill the dropdown filters."""
        couriers = self._run(
            "SELECT DISTINCT courier_id FROM Requests "
            "WHERE courier_id IS NOT NULL ORDER BY courier_id")
        states = self._run(
            "SELECT DISTINCT state FROM Requests WHERE state IS NOT NULL")
        items = self._run("SELECT DISTINCT item_name FROM Inventory ORDER BY item_name")
        return {
            "couriers": [r["courier_id"] for r in couriers],
            "states": sorted(set(self.KNOWN_STATES) | {r["state"] for r in states}),
            "items": [r["item_name"] for r in items],
        }

    def get_stock(self, item_or_sku):
        """Return (item_name, total_available) matching an item name or SKU, else None."""
        rows = self._run(
            """SELECT item_name, SUM(quantity) AS available
               FROM Inventory
               WHERE item_name = %s OR sku_id = %s
               GROUP BY item_name""",
            (item_or_sku, item_or_sku),
        )
        if not rows:
            return None
        return rows[0]["item_name"], int(rows[0]["available"] or 0)

    # ---- requesting ----
    def insert_request(self, item_name, quantity, requester_id, courier_id=None, state="Pending"):
        return self._run(
            """INSERT INTO Requests
                   (item_name, quantity, date_time, courier_id, requester_id, state)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (item_name, quantity, datetime.now(), courier_id, requester_id, state),
            write=True,
        )


# --------------------------------------------------------------------------- #
# Small reusable widgets
# --------------------------------------------------------------------------- #
class Badge(ctk.CTkLabel):
    """Small rounded pill label. kind: 'success' | 'warning' | 'neutral'."""

    STYLES = {
        "success": (Theme.PRIMARY_SOFT, Theme.PRIMARY),
        "warning": (Theme.WARN_SOFT, Theme.WARN_TEXT),
        "neutral": (Theme.PRIMARY_SOFT, Theme.TEXT),
    }

    def __init__(self, master, text="", kind="success", **kw):
        bg, fg = self.STYLES[kind]
        super().__init__(
            master, text=text, fg_color=bg, text_color=fg,
            corner_radius=6, height=22, font=Theme.font(10, "bold"), **kw,
        )


class Card(ctk.CTkFrame):
    """White rounded container with a thin border."""

    def __init__(self, master, **kw):
        super().__init__(
            master, fg_color=Theme.CARD, border_color=Theme.BORDER,
            border_width=1, corner_radius=10, **kw,
        )


class SearchBox(ctk.CTkEntry):
    def __init__(self, master, placeholder="Search", width=240, **kw):
        super().__init__(
            master, placeholder_text=placeholder, width=width, height=34,
            fg_color=Theme.CARD, border_color=Theme.BORDER, border_width=1,
            text_color=Theme.TEXT, font=Theme.font(11), **kw,
        )


class FilterBox(ctk.CTkComboBox):
    def __init__(self, master, values, width=150, **kw):
        super().__init__(
            master, values=values, width=width, height=34, state="readonly",
            fg_color=Theme.CARD, border_color=Theme.BORDER, border_width=1,
            button_color=Theme.CARD, button_hover_color=Theme.TABLE_HEAD,
            text_color=Theme.MUTED, dropdown_font=Theme.font(11),
            font=Theme.font(11), **kw,
        )
        self.set(values[0])


class PrimaryButton(ctk.CTkButton):
    def __init__(self, master, text, **kw):
        # Defaults that callers can override (e.g. height=38)
        kw.setdefault("height", 34)
        kw.setdefault("corner_radius", 6)
        kw.setdefault("font", Theme.font(12, "bold"))
        super().__init__(
            master, text=text, fg_color=Theme.PRIMARY,
            hover_color=Theme.PRIMARY_HOVER, text_color="white", **kw,
        )


class DataTable(ctk.CTkFrame):
    """
    Fixed header + vertically scrollable body.

    columns: list of (title, min_width, weight)
    Add data with:
        table.add_row(["REQ-1", "Item", ...])
    A cell may also be a callable(parent) -> widget (e.g. to put a Badge in a cell):
        table.add_row(["REQ-1", lambda p: Badge(p, "Ready")])
    """

    ROWS_PER_TICK = 25   # rows built per UI tick, so big tables never freeze the window

    def __init__(self, master, columns, height=260):
        super().__init__(master, fg_color="transparent")
        self.columns = columns
        self._render_token = 0
        self.grid_columnconfigure(0, weight=1)

        # header
        self.header = ctk.CTkFrame(self, fg_color=Theme.TABLE_HEAD, corner_radius=0, height=32)
        self.header.grid(row=0, column=0, sticky="ew")
        self._configure_columns(self.header)
        for i, (title, _, _) in enumerate(columns):
            ctk.CTkLabel(
                self.header, text=title, anchor="w",
                text_color=Theme.MUTED, font=Theme.font(10, "bold"),
            ).grid(row=0, column=i, sticky="ew", padx=(12 if i == 0 else 4, 4), pady=7)

        # scrollable body
        self.body = ctk.CTkScrollableFrame(
            self, fg_color=Theme.CARD, corner_radius=0, height=height,
            scrollbar_button_color=Theme.BORDER,
            scrollbar_button_hover_color=Theme.MUTED,
        )
        self.body.grid(row=1, column=0, sticky="ew")
        self.body.grid_columnconfigure(0, weight=1)
        self._row_count = 0

    def _configure_columns(self, frame):
        for i, (_, minw, weight) in enumerate(self.columns):
            frame.grid_columnconfigure(i, weight=weight, minsize=minw)

    # ---- public API ----
    # NOTE: rows use plain tkinter widgets on purpose. CustomTkinter widgets are very slow
    # to create (a few hundred rows can freeze the window for seconds).
    def add_row(self, values):
        row = tk.Frame(self.body, bg=Theme.CARD)
        row.grid(row=self._row_count * 2, column=0, sticky="ew")
        self._configure_columns(row)
        for i, v in enumerate(values):
            pad = (12 if i == 0 else 4, 4)
            if callable(v):
                v(row).grid(row=0, column=i, sticky="w", padx=pad, pady=10)
            else:
                tk.Label(
                    row, text=str(v), anchor="w", bg=Theme.CARD, fg=Theme.TEXT,
                    font=Theme.tkfont(11),
                ).grid(row=0, column=i, sticky="ew", padx=pad, pady=10)
        tk.Frame(self.body, height=1, bg=Theme.BORDER).grid(
            row=self._row_count * 2 + 1, column=0, sticky="ew")
        self._row_count += 1
        return row

    def set_rows(self, rows):
        """Replace the table contents. Rows are built a few at a time (non-blocking)."""
        self.clear()
        token = self._render_token

        def step(start):
            if token != self._render_token:   # a newer set_rows()/clear() took over
                return
            for values in rows[start:start + self.ROWS_PER_TICK]:
                self.add_row(values)
            if start + self.ROWS_PER_TICK < len(rows):
                self.after(10, lambda: step(start + self.ROWS_PER_TICK))

        step(0)

    def clear(self):
        self._render_token += 1   # cancels any render still in progress
        for child in self.body.winfo_children():
            child.destroy()
        self._row_count = 0


# --------------------------------------------------------------------------- #
# Top bar and sidebar
# --------------------------------------------------------------------------- #
class TopBar(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=Theme.CARD, corner_radius=0, height=62)
        self.grid_columnconfigure(1, weight=1)
        self.grid_propagate(False)

        logo = ctk.CTkLabel(self, text="🏥", width=36, height=36, corner_radius=8,
                            fg_color=Theme.PRIMARY_SOFT, font=Theme.font(16))
        logo.grid(row=0, column=0, padx=(18, 10), pady=12)
        ctk.CTkLabel(self, text="Hospital IAM Sorting Hub", text_color=Theme.TEXT,
                     font=Theme.font(15, "bold")).grid(row=0, column=1, sticky="w")

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=2, padx=18, sticky="e")

        self.network_label = ctk.CTkLabel(
            right, text="●  Local network · Sample data",
            text_color=Theme.MUTED, font=Theme.font(10))
        self.network_label.grid(row=0, column=0, padx=(0, 16))

        self.avatar = ctk.CTkLabel(right, text="", width=30, height=30, corner_radius=15,
                                   fg_color=Theme.PRIMARY_SOFT, text_color=Theme.TEXT,
                                   font=Theme.font(10, "bold"))
        self.avatar.grid(row=0, column=1, padx=(0, 8))

        info = ctk.CTkFrame(right, fg_color="transparent")
        info.grid(row=0, column=2, padx=(0, 12))
        self.user_name = ctk.CTkLabel(info, text="", anchor="w", text_color=Theme.TEXT,
                                      font=Theme.font(10, "bold"))
        self.user_name.pack(anchor="w")
        self.user_role = ctk.CTkLabel(info, text="", anchor="w", text_color=Theme.MUTED,
                                      font=Theme.font(9))
        self.user_role.pack(anchor="w")

        self.access_badge = Badge(right, text="", kind="success")
        self.access_badge.grid(row=0, column=3)


class Sidebar(ctk.CTkFrame):
    ITEMS = [
        ("Package Monitor", "▦"),
        ("Inventory Terminal", "⬡"),
        ("Package Receive", "⌗"),
        ("Holds & Review", "⛉"),
        ("Audit Log", "▤"),
        ("Sign out", "▤"),
    ]

    def __init__(self, master, on_select=None):
        super().__init__(master, fg_color=Theme.CARD, corner_radius=0, width=188)
        self.grid_propagate(False)
        self.on_select = on_select
        self.buttons = {}
        for i, (name, icon) in enumerate(self.ITEMS):
            btn = ctk.CTkButton(
                self, text=f"  {icon}   {name}", anchor="w", height=36, corner_radius=8,
                fg_color="transparent", hover_color=Theme.TABLE_HEAD,
                text_color=Theme.MUTED, font=Theme.font(11),
                command=lambda n=name: self.select(n),
            )
            btn.pack(fill="x", padx=12, pady=(22 if i == 0 else 3, 0))
            self.buttons[name] = btn
        self.select("Package Monitor", notify=False)

    def select(self, name, notify=True):
        for n, b in self.buttons.items():
            active = n == name
            b.configure(fg_color=Theme.PRIMARY_SOFT if active else "transparent",
                        text_color=Theme.PRIMARY if active else Theme.MUTED)
        if notify and self.on_select:
            self.on_select(name)  # TODO: switch pages here


# --------------------------------------------------------------------------- #
# Page sections
# --------------------------------------------------------------------------- #
class PageHeader(ctk.CTkFrame):
    def __init__(self, master, title, on_request=None):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title, text_color=Theme.TEXT,
                     font=Theme.font(24, "bold")).grid(row=0, column=0, sticky="w")
        PrimaryButton(self, "+   Request item", width=120, height=38,
                      command=on_request).grid(row=0, column=1, sticky="e")


class DeliveriesCard(Card):
    COLUMNS = [
        ("Request ID", 90, 1), ("Item / SKU", 150, 2), ("Qty", 50, 1),
        ("Date & Time", 90, 1), ("Courier", 80, 1), ("Requester", 90, 1),
        ("Destination", 110, 1), ("State", 90, 1),
    ]

    def __init__(self, master):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        top.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(top, text="In-progress deliveries", text_color=Theme.TEXT,
                     font=Theme.font(13, "bold")).grid(row=0, column=0, sticky="w")
        self.view_badge = Badge(top, text="")
        self.view_badge.grid(row=0, column=1, padx=10)
        self.snapshot_label = ctk.CTkLabel(top, text="", text_color=Theme.MUTED,
                                           font=Theme.font(10))
        self.snapshot_label.grid(row=0, column=2, sticky="e")

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        filters.grid_columnconfigure(3, weight=1)
        self.search = SearchBox(filters, "Search Request ID or item", width=245)
        self.search.grid(row=0, column=0, padx=(0, 8))
        self.courier_filter = FilterBox(filters, ["All couriers"], width=150)
        self.courier_filter.grid(row=0, column=1, padx=(0, 8))
        self.state_filter = FilterBox(filters, ["All states"], width=130)
        self.state_filter.grid(row=0, column=2)
        self.count_label = ctk.CTkLabel(filters, text="", text_color=Theme.MUTED,
                                        font=Theme.font(10))
        self.count_label.grid(row=0, column=3, sticky="e")

        self.table = DataTable(self, self.COLUMNS, height=300)
        self.table.grid(row=2, column=0, sticky="ew", padx=1, pady=(0, 1))


class HoldBanner(ctk.CTkFrame):
    def __init__(self, master, on_open=None):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        box = ctk.CTkFrame(self, fg_color=Theme.WARN_BG, corner_radius=8)
        box.grid(row=0, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(box, text="⚠", text_color=Theme.WARN_TEXT,
                     font=Theme.font(14)).grid(row=0, column=0, padx=(12, 8), pady=12, sticky="n")
        text = ctk.CTkFrame(box, fg_color="transparent")
        text.grid(row=0, column=1, sticky="w", pady=10)
        self.title_label = ctk.CTkLabel(text, text="", anchor="w", text_color=Theme.WARN_TEXT,
                                        font=Theme.font(11, "bold"))
        self.title_label.pack(anchor="w")
        self.detail_label = ctk.CTkLabel(text, text="", anchor="w", justify="left",
                                         text_color=Theme.WARN_TEXT, font=Theme.font(10))
        self.detail_label.pack(anchor="w")

        link = ctk.CTkButton(self, text="Open holds & review →", width=0, height=20,
                             fg_color="transparent", hover=False, text_color=Theme.PRIMARY,
                             font=Theme.font(10, "bold"), anchor="w", command=on_open)
        link.grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.release_label = ctk.CTkLabel(self, text="", text_color=Theme.MUTED,
                                          font=Theme.font(9))
        self.release_label.grid(row=1, column=1, sticky="e", pady=(8, 0))


class InventoryCard(Card):
    COLUMNS = [
        ("Item / SKU", 150, 2), ("Available", 80, 1), ("Sensitivity", 100, 1),
        ("Department", 110, 1), ("Package ID", 100, 1),
    ]

    def __init__(self, master):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        top.grid_columnconfigure(0, weight=1)
        titles = ctk.CTkFrame(top, fg_color="transparent")
        titles.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(titles, text="Available inventory", text_color=Theme.TEXT,
                     font=Theme.font(13, "bold")).pack(anchor="w")
        self.subtitle_label = ctk.CTkLabel(titles, text="", text_color=Theme.MUTED,
                                           font=Theme.font(9))
        self.subtitle_label.pack(anchor="w")
        self.scope_badge = Badge(top, text="")
        self.scope_badge.grid(row=0, column=1, sticky="ne")

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        filters.grid_columnconfigure(3, weight=1)
        self.search = SearchBox(filters, "Search item or SKU", width=220)
        self.search.grid(row=0, column=0, padx=(0, 8))
        self.item_filter = FilterBox(filters, ["All items"], width=140)
        self.item_filter.grid(row=0, column=1, padx=(0, 8))
        self.level_filter = FilterBox(filters, ["All stock levels"], width=150)
        self.level_filter.grid(row=0, column=2)
        self.count_label = ctk.CTkLabel(filters, text="", text_color=Theme.MUTED,
                                        font=Theme.font(10))
        self.count_label.grid(row=0, column=3, sticky="e")

        self.table = DataTable(self, self.COLUMNS, height=260)
        self.table.grid(row=2, column=0, sticky="ew", padx=1, pady=(0, 1))


class RequestForm(Card):
    def __init__(self, master, on_submit=None):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(top, text="Request inventory", text_color=Theme.TEXT,
                     font=Theme.font(13, "bold")).grid(row=0, column=0, sticky="w")
        self.sensitivity_badge = Badge(top, text="")
        self.sensitivity_badge.grid(row=0, column=1, sticky="e")

        self.item_entry = self._field("Item / SKU", 1)
        self.qty_entry = self._field("Quantity", 2)
        self.requester_entry = self._field("Requester", 3)
        self.destination_entry = self._field("Destination", 4)

        ctk.CTkLabel(self, text="Approval", anchor="w", text_color=Theme.MUTED,
                     font=Theme.font(10)).grid(row=5, column=0, sticky="w", padx=14, pady=(10, 0))
        self.approval_label = ctk.CTkLabel(
            self, text="", anchor="w", justify="left", wraplength=230,
            text_color=Theme.TEXT, font=Theme.font(10))
        self.approval_label.grid(row=6, column=0, sticky="w", padx=14)

        self.submit_button = PrimaryButton(self, "Submit request", width=120, command=on_submit)
        self.submit_button.grid(row=7, column=0, sticky="w", padx=14, pady=(10, 16))

    def _field(self, label, row):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=row, column=0, sticky="ew", padx=14, pady=(4, 0))
        wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(wrap, text=label, anchor="w", text_color=Theme.MUTED,
                     font=Theme.font(10)).grid(row=0, column=0, sticky="w")
        entry = ctk.CTkEntry(wrap, height=34, fg_color=Theme.CARD, border_color=Theme.BORDER,
                             border_width=1, text_color=Theme.TEXT, font=Theme.font(11))
        entry.grid(row=1, column=0, sticky="ew")
        return entry


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
class PackageMonitorPage(ctk.CTkScrollableFrame):
    """Main page. Scrolls vertically if the window is small."""

    REFRESH_MS = 10_000          # auto-refresh interval
    HANG_WARNING_SECONDS = 8     # warn if a database call takes longer than this
    MAX_ROWS = 300               # rows shown per table (use search/filters to narrow down)

    STATUS_COLORS = {
        "error": (Theme.ERROR_BG, Theme.ERROR_TEXT),
        "warning": (Theme.WARN_BG, Theme.WARN_TEXT),
        "success": (Theme.PRIMARY_SOFT, Theme.PRIMARY),
    }

    def __init__(self, master, db):
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self.db = db
        self.grid_columnconfigure(0, weight=1)

        self.header = PageHeader(self, "Package Monitor", on_request=self.on_request_item)
        self.header.grid(row=0, column=0, sticky="ew", padx=22, pady=(22, 14))

        # In-app message banner (hidden until there is something to say)
        self.status = ctk.CTkLabel(
            self, text="", anchor="w", justify="left", wraplength=880,
            corner_radius=8, font=Theme.font(11))
        self.status.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 12))
        self.status.grid_remove()
        self._status_kind = None
        self._status_token = 0

        self.deliveries = DeliveriesCard(self)
        self.deliveries.grid(row=2, column=0, sticky="ew", padx=22)

        self.holds = HoldBanner(self, on_open=self.on_open_holds)
        self.holds.grid(row=3, column=0, sticky="ew", padx=22, pady=14)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=4, column=0, sticky="ew", padx=22, pady=(0, 22))
        bottom.grid_columnconfigure(0, weight=3)
        bottom.grid_columnconfigure(1, weight=1, minsize=270)

        self.inventory = InventoryCard(bottom)
        self.inventory.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.request_form = RequestForm(bottom, on_submit=self.on_submit_request)
        self.request_form.grid(row=0, column=1, sticky="new")

        # background-thread plumbing
        self._results = queue.Queue()   # results coming back from worker threads
        self._latest = {}               # key -> newest call number (drops stale results)
        self._inflight = {}             # call id -> start time of running calls
        self._call_id = 0
        self._signatures = {}           # table -> fingerprint of what is on screen
        self._timers = {}               # debounce timers for the search boxes

        self._wire_events()
        self._poll_results()
        self._watchdog()
        self.after(300, self._auto_refresh)   # first load, after the window has drawn

    # ------------------------------------------------------------------ #
    # Status banner (replaces popups)
    # ------------------------------------------------------------------ #
    def set_status(self, text="", kind="error", clear_after=None):
        self._status_token += 1
        token = self._status_token
        if not text:
            self._status_kind = None
            self.status.grid_remove()
            return
        self._status_kind = kind
        bg, fg = self.STATUS_COLORS[kind]
        self.status.configure(text=f"  {text}", fg_color=bg, text_color=fg)
        self.status.grid()
        if clear_after:
            self.after(clear_after,
                       lambda: self.set_status("") if token == self._status_token else None)

    def _show_error(self, err):
        traceback.print_exception(type(err), err, err.__traceback__)  # full details in terminal
        self.set_status(f"Database error ({type(err).__name__}): {err}", "error")

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #
    def _wire_events(self):
        d, inv = self.deliveries, self.inventory

        d.state_filter.configure(values=["All states", *Database.KNOWN_STATES],
                                 command=lambda _v: self.load_requests())
        d.courier_filter.configure(command=lambda _v: self.load_requests())
        d.search.bind("<KeyRelease>",
                      lambda _e: self._debounce("req_search", self.load_requests))

        inv.item_filter.configure(command=lambda _v: self.load_inventory())
        inv.level_filter.configure(values=["All stock levels", *Database.LEVELS],
                                   command=lambda _v: self.load_inventory())
        inv.level_filter.set("All stock levels")
        inv.search.bind("<KeyRelease>",
                        lambda _e: self._debounce("inv_search", self.load_inventory))

    def _debounce(self, key, fn, delay=300):
        """Run fn once the user has stopped typing for `delay` ms."""
        pending = self._timers.pop(key, None)
        if pending:
            self.after_cancel(pending)
        self._timers[key] = self.after(delay, fn)

    def _auto_refresh(self):
        if not self._inflight:  # don't pile up calls while the database is slow/down
            self.refresh()
        self.after(self.REFRESH_MS, self._auto_refresh)

    def refresh(self):
        self.load_options()
        self.load_requests()
        self.load_holds()
        self.load_inventory()

    # ------------------------------------------------------------------ #
    # Background database plumbing (keeps the UI responsive)
    # ------------------------------------------------------------------ #
    def _background(self, key, work, on_done):
        """Run work() in a thread; on_done(result) is then called on the UI thread."""
        self._call_id += 1
        call_id = self._call_id
        self._latest[key] = call_id
        self._inflight[call_id] = time.monotonic()

        def runner():
            try:
                result, err = work(), None
            except Exception as e:  # includes network/SSL errors, not just mysql errors
                result, err = None, e
            self._results.put((call_id, key, on_done, result, err))

        threading.Thread(target=runner, daemon=True).start()

    def _poll_results(self):
        try:
            while True:
                call_id, key, on_done, result, err = self._results.get_nowait()
                self._inflight.pop(call_id, None)
                if key == "submit":
                    self.request_form.submit_button.configure(state="normal")
                if call_id != self._latest.get(key):
                    continue  # a newer call for this key superseded it
                if err is not None:
                    self._show_error(err)
                    continue
                try:
                    on_done(result)
                except Exception as e:
                    self._show_error(e)
        except queue.Empty:
            pass
        finally:
            self.after(100, self._poll_results)

    def _watchdog(self):
        """Tell the user if a database call is stuck instead of failing silently."""
        if self._inflight:
            oldest = min(self._inflight.values())
            if time.monotonic() - oldest > self.HANG_WARNING_SECONDS:
                self.set_status(
                    "The database is not responding. Check that MySQL is running and that "
                    "mysql-connector-python is up to date "
                    "(pip install --upgrade mysql-connector-python).", "error")
        self.after(2000, self._watchdog)

    # ------------------------------------------------------------------ #
    # Cell builders (return a function that builds a widget inside a table row)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _item_cell(name, sku):
        def build(parent):
            f = tk.Frame(parent, bg=Theme.CARD)
            tk.Label(f, text=name or "", anchor="w", bg=Theme.CARD, fg=Theme.TEXT,
                     font=Theme.tkfont(11, "bold")).pack(anchor="w")
            tk.Label(f, text=f"SKU {sku}" if sku else "", anchor="w", bg=Theme.CARD,
                     fg=Theme.MUTED, font=Theme.tkfont(9)).pack(anchor="w")
            return f
        return build

    @staticmethod
    def _state_cell(state):
        bg, fg = {
            "Ready": (Theme.PRIMARY_SOFT, Theme.PRIMARY),
            "Held": (Theme.WARN_SOFT, Theme.WARN_TEXT),
        }.get(state, (Theme.PRIMARY_SOFT, Theme.TEXT))
        return lambda parent: tk.Label(
            parent, text=state or "—", bg=bg, fg=fg,
            font=Theme.tkfont(10, "bold"), padx=8, pady=2)

    @staticmethod
    def _fmt_time(value):
        return value.strftime("%H:%M") if isinstance(value, datetime) else ""

    @staticmethod
    def _selected(box, all_label):
        """Value of a filter dropdown, or None when it is on its 'All ...' option."""
        value = box.get()
        return None if value == all_label else value

    @staticmethod
    def _set_options(box, all_label, values):
        options = [all_label, *values]
        current = box.get()
        box.configure(values=options)
        if current not in options:
            box.set(all_label)

    # ------------------------------------------------------------------ #
    # Loading data into the UI
    # ------------------------------------------------------------------ #
    def load_options(self):
        self._background("options", self.db.fetch_filter_options, self._show_options)

    def _show_options(self, opts):
        self._set_options(self.deliveries.courier_filter, "All couriers", opts["couriers"])
        self._set_options(self.deliveries.state_filter, "All states", opts["states"])
        self._set_options(self.inventory.item_filter, "All items", opts["items"])

    def load_requests(self):
        d = self.deliveries
        search = d.search.get().strip()
        state = self._selected(d.state_filter, "All states")
        courier = self._selected(d.courier_filter, "All couriers")
        self._background("requests",
                         lambda: self.db.fetch_requests(search, state, courier),
                         self._show_requests)

    def _show_requests(self, rows):
        d = self.deliveries
        shown = rows[:self.MAX_ROWS]
        # Only rebuild the table when something actually changed
        sig = tuple((r["request_no"], r["item_name"], r["quantity"], r["date_time"],
                     r["courier_id"], r["requester_id"], r["state"]) for r in shown)
        if sig != self._signatures.get("requests"):
            self._signatures["requests"] = sig
            d.table.set_rows([[
                f"REQ-{r['request_no']}",
                self._item_cell(r["item_name"], r["sku_id"]),
                r["quantity"],
                self._fmt_time(r["date_time"]),
                r["courier_id"] or "",
                r["requester_id"] or "",
                "—",  # Destination: no column in Requests yet
                self._state_cell(r["state"]),
            ] for r in shown])
        ready = sum(1 for r in rows if r["state"] == "Ready")
        total = (f"{len(rows)} requests" if len(rows) <= self.MAX_ROWS
                 else f"Showing {self.MAX_ROWS} of {len(rows)} requests")
        d.count_label.configure(text=f"{total} · {ready} ready")
        d.snapshot_label.configure(text=f"Snapshot {datetime.now():%H:%M}")
        if self._status_kind == "error":   # a successful load clears an old error
            self.set_status("")

    def load_holds(self):
        self._background("holds", lambda: self.db.fetch_requests(state="Held"),
                         self._show_holds)

    def _show_holds(self, held):
        n = len(held)
        if n:
            lines = [f"REQ-{r['request_no']} · {r['item_name']}" for r in held[:5]]
            if n > 5:
                lines.append(f"… and {n - 5} more")
            self.holds.title_label.configure(text=f"{n} item{'s' if n != 1 else ''} on hold")
            self.holds.detail_label.configure(text="\n".join(lines))
        else:
            self.holds.title_label.configure(text="No items on hold")
            self.holds.detail_label.configure(text="")

    def load_inventory(self):
        inv = self.inventory
        search = inv.search.get().strip()
        item = self._selected(inv.item_filter, "All items")
        level = self._selected(inv.level_filter, "All stock levels")
        self._background("inventory",
                         lambda: self.db.fetch_inventory(search, item, level),
                         self._show_inventory)

    def _show_inventory(self, rows):
        inv = self.inventory
        shown = rows[:self.MAX_ROWS]
        sig = tuple((r["item_name"], r["sku_id"], r["quantity"], r["package_id"])
                    for r in shown)
        if sig != self._signatures.get("inventory"):
            self._signatures["inventory"] = sig
            inv.table.set_rows([[
                self._item_cell(r["item_name"], r["sku_id"]),
                r["quantity"],
                "—",  # Sensitivity: no column in Inventory yet
                "—",  # Department: no column in Inventory yet
                r["package_id"] or "",
            ] for r in shown])
        total = (f"{len(rows)} available items" if len(rows) <= self.MAX_ROWS
                 else f"Showing {self.MAX_ROWS} of {len(rows)} items")
        inv.count_label.configure(text=total)

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def on_request_item(self):
        self.request_form.item_entry.focus()

    def on_open_holds(self):
        pass  # TODO: navigate to the Holds & Review page

    def on_submit_request(self):
        form = self.request_form
        item = form.item_entry.get().strip()
        qty_text = form.qty_entry.get().strip()
        requester = form.requester_entry.get().strip()
        # NOTE: the Destination field is not saved - the Requests table has no column for it.

        if not item or not requester:
            self.set_status("Enter an item/SKU and a requester.", "warning", 6000)
            return
        if not qty_text.isdigit() or int(qty_text) <= 0:
            self.set_status("Quantity must be a whole number above 0.", "warning", 6000)
            return
        qty = int(qty_text)

        def work():  # runs in a background thread
            stock = self.db.get_stock(item)
            if stock is None:
                return ("missing", None, 0)
            name, available = stock
            if qty > available:
                return ("short", name, available)
            # TODO: decrement Inventory, set courier_id, apply approval rules, etc.
            self.db.insert_request(name, qty, requester)
            return ("ok", name, available)

        def done(result):  # runs on the UI thread
            status, name, available = result
            if status == "missing":
                self.set_status(f"No inventory item matches '{item}'.", "warning", 6000)
            elif status == "short":
                self.set_status(f"Only {available} of {name} available.", "warning", 6000)
            else:
                for entry in (form.item_entry, form.qty_entry,
                              form.requester_entry, form.destination_entry):
                    entry.delete(0, "end")
                self.set_status(f"Request submitted: {qty} × {name}.", "success", 6000)
                self.refresh()

        form.submit_button.configure(state="disabled")  # prevent double submits
        self._background("submit", work, done)


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Hospital IAM Sorting Hub")
        self.geometry("1280x900")
        self.minsize(1000, 650)
        self.configure(fg_color=Theme.BG)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.topbar = TopBar(self)
        self.topbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        ctk.CTkFrame(self, height=1, fg_color=Theme.BORDER, corner_radius=0).grid(
            row=0, column=0, columnspan=2, sticky="sew")

        self.sidebar = Sidebar(self, on_select=self.navigate)
        self.sidebar.grid(row=1, column=0, sticky="ns")

        self.db = Database(DB_CONFIG)
        self.page = PackageMonitorPage(self, self.db)
        self.page.grid(row=1, column=1, sticky="nsew")

        self._heartbeat()

    def _heartbeat(self):
        """Self-diagnosis: if the UI is stuck for 10 s, Python prints where it is stuck."""
        faulthandler.cancel_dump_traceback_later()
        faulthandler.dump_traceback_later(10)
        self.after(500, self._heartbeat)

    def navigate(self, name):
        pass  # TODO: swap pages depending on `name`


if __name__ == "__main__":
    App().mainloop()