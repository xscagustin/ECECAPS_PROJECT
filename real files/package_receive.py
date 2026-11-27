"""
package_receive.py
------------------
"Package Receive" tab for the Hospital IAM Sorting Hub.
 
Flow (see Chapter 4, sections 4.1.6 and 4.2.1):
    1. The courier generates a signed QR in the Inventory Terminal. That page
       saves it in the QrCodes table and sets the request to "Ready".
    2. The receiver (on any department PC) opens this tab and scans the QR.
    3. This page decodes the QR and verifies its HMAC-SHA-256 tag.
    4. It checks the QR really was issued (QrCodes) and is still Active,
       then runs the release rules against the Requests table.
    5. It shows Permit / Deny / Hold. On Permit the QR is marked "Claimed" and
       the request is marked "Delivered".
 
Libraries:
    pip install customtkinter opencv-python pillow qrcode mysql-connector-python
 
Database assumptions:
    Requests  : request_id, item_name, quantity, date, time, courier_id,
                requester_id, state, Department, Approval
                (state 'Ready' = ready to claim)
    QrCodes   : request_id, tag, status ('Active' / 'Claimed' / 'Void'), ...
                (created by inventory_terminal.py)
    AuditLog  : timestamp, employee_id, request_id, sku_id,
                compartment_id, decision, reason
 
CHANGES in this version (marked with "NEW" below):
    - The QR must match an Active row in QrCodes (blocks copied / reused /
      voided / never-issued labels, even if the signature is valid).
    - On Permit, QrCodes.status becomes 'Claimed'.
    - The request state on Permit is now 'Delivered' (was 'Claimed') so it
      matches the states used by the Package Monitor.
"""
 
import hmac
import hashlib
import json
from datetime import datetime
 
import cv2                      # camera + QR decoding
import customtkinter as ctk
from PIL import Image
 
# Key held ONLY on the server. Load it from an environment variable in real use.
# It must be identical on every PC that creates or scans QR codes.
SECRET_KEY = b"change-this-secret-key"
 
# State a request gets once the receiver has successfully claimed it
CLAIMED_STATE = "Delivered"
 
# Higher number = more sensitive. A user's level must be >= the item's class.
SENSITIVITY_RANK = {"Routine": 1, "Sensitive": 2}
ACCESS_RANK = {"Medical Staff": 1, "Departmental": 2, "Courier": 2, "Administrative": 3}
 
 
# ---------------------------------------------------------------------------
# QR helpers (plain functions - no class needed)
# ---------------------------------------------------------------------------
def sign_fields(fields: dict) -> str:
    """Return the HMAC-SHA-256 tag (hex) for the QR fields."""
    message = json.dumps(fields, sort_keys=True).encode()
    return hmac.new(SECRET_KEY, message, hashlib.sha256).hexdigest()
 
 
def verify_qr_text(text: str):
    """Decode the QR text and check its tag.
    Returns (fields dict, tag) or (None, None)."""
    try:
        payload = json.loads(text)
        tag = payload.pop("tag")
    except (ValueError, KeyError, AttributeError):
        return None, None
    # compare_digest avoids timing attacks
    if hmac.compare_digest(tag, sign_fields(payload)):
        return payload, tag
    return None, None
 
 
# ---------------------------------------------------------------------------
# The tab itself
# ---------------------------------------------------------------------------
class PackageReceivePage(ctk.CTkFrame):
    """One frame that app.py places inside a tab (app.py calls pack())."""
 
    def __init__(self, parent, cursor, user):
        """
        parent : the tab this page is placed in
        cursor : the shared MySQL cursor from app.py (autocommit is on)
        user   : dict from app.py, e.g.
                 {"id": "PH-219", "name": "Maya Chen",
                  "role": "Departmental", "department": "Pharmacy"}
        """
        super().__init__(parent)
        self.cursor = cursor
        self.user = user
        self.camera = None                       # cv2.VideoCapture when scanning
        self.detector = cv2.QRCodeDetector()
 
        # ---- left side: camera preview and scan button ----
        self.preview = ctk.CTkLabel(self, text="Camera is off", width=400, height=300,
                                    fg_color="gray20")
        self.preview.grid(row=0, column=0, padx=20, pady=20)
 
        self.scan_button = ctk.CTkButton(self, text="Scan QR", command=self.start_scan)
        self.scan_button.grid(row=1, column=0, pady=(0, 20))
 
        # ---- right side: decoded details and the decision ----
        self.result_label = ctk.CTkLabel(self, text="Waiting for scan",
                                         font=("Arial", 22, "bold"))
        self.result_label.grid(row=0, column=1, padx=20, sticky="s")
 
        self.details = ctk.CTkTextbox(self, width=320, height=220)
        self.details.grid(row=1, column=1, padx=20, pady=(0, 20), sticky="n")
 
    # ------------------------------------------------------------------
    # Camera handling
    # ------------------------------------------------------------------
    def start_scan(self):
        """Open the camera and start the frame loop."""
        if self.camera is not None:
            return
        self.camera = cv2.VideoCapture(0)
        if not self.camera.isOpened():
            self.camera = None
            self.show_result("Camera unavailable", "orange", "Use manual lookup.")
            return
        self.show_result("Scanning...", "white", "")
        self.scan_button.configure(state="disabled")
        self.update_frame()
 
    def stop_scan(self):
        """Release the camera and reset the preview."""
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        self.preview.configure(image=None, text="Camera is off")
        self.scan_button.configure(state="normal")
 
    def update_frame(self):
        """Read one frame, show it, try to decode a QR, then schedule itself again."""
        if self.camera is None:
            return
        ok, frame = self.camera.read()
        if not ok:
            self.stop_scan()
            self.show_result("Camera error", "orange", "Fell back to manual entry.")
            return
 
        # Show the frame (OpenCV uses BGR, Pillow wants RGB)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = ctk.CTkImage(Image.fromarray(rgb), size=(400, 300))
        self.preview.configure(image=image, text="")
        self.preview.image = image               # keep a reference so it isn't garbage collected
 
        # Try to decode a QR code in this frame
        text, _, _ = self.detector.detectAndDecode(frame)
        if text:
            self.stop_scan()
            self.process_qr(text)
        else:
            self.after(30, self.update_frame)    # check again in 30 ms
 
    # ------------------------------------------------------------------
    # Release rules (4.1.6) - first failure decides
    # ------------------------------------------------------------------
    def process_qr(self, text):
        """Run the release rules on the scanned text and show the decision."""
        decision, reason, fields = self.decide(text)
        self.show_result(decision, {"Permit": "green", "Hold": "orange"}.get(decision, "red"), reason)
 
        if fields:
            self.details.insert("end", "\n".join(f"{k}: {v}" for k, v in fields.items()))
        if decision == "Permit":
            # Mark the request delivered and the QR as used (blocks reuse)
            self.set_state(fields["request_id"], CLAIMED_STATE)
            self.mark_qr_claimed(fields["request_id"])
        self.log_decision(decision, reason, fields)
 
    def decide(self, text):
        """Return (decision, reason, qr_fields). Any unexpected error -> Deny."""
        fields = None
        try:
            # Rule 1: valid login session (the app only creates this tab after login)
            if not self.user:
                return "Deny", "No valid session", None
 
            # Rule 2: QR decodes and HMAC verifies
            fields, tag = verify_qr_text(text)
            if fields is None:
                return "Deny", "Invalid token", None
 
            # Rule 3: request exists, approved and ready to claim
            self.cursor.execute("SELECT state, requester_id FROM Requests WHERE request_id = %s",
                                (fields["request_id"],))
            row = self.cursor.fetchone()
            self.cursor.fetchall()               # clear any leftovers
            if row is None:
                return "Deny", "Request not found", fields
            state, requester_id = row
 
            # NEW - Rule 3a: this exact QR must have been issued by the
            # Inventory Terminal and still be Active (not Claimed / Void).
            self.cursor.execute(
                "SELECT status FROM QrCodes WHERE request_id = %s AND tag = %s "
                "ORDER BY qr_id DESC LIMIT 1", (fields["request_id"], tag))
            qr_row = self.cursor.fetchone()
            self.cursor.fetchall()
            if qr_row is None:
                return "Deny", "QR was not issued by the Inventory Terminal", fields
            if qr_row[0] == "Claimed":
                return "Deny", "QR already claimed", fields
            if qr_row[0] != "Active":
                return "Deny", f"QR is {qr_row[0]}", fields
 
            if state == "On Hold":
                return "Hold", "Request is on hold", fields
            if state != "Ready":
                return "Deny", f"Request is {state}, not ready to claim", fields
 
            # Rule 5: department matches the destination
            if self.user["department"] != fields["destination"]:
                return "Deny", "Wrong department", fields
 
            # Rule 6: access level meets the sensitivity class
            needed = SENSITIVITY_RANK.get(fields["sensitivity"], 99)
            if ACCESS_RANK.get(self.user["role"], 0) < needed:
                return "Deny", "Insufficient level", fields
 
            # Rule 7: sensitive items go to the requester or the Department Head
            # (here "Departmental" and "Administrative" roles count as head)
            if fields["sensitivity"] == "Sensitive":
                is_requester = self.user["id"] == requester_id
                is_head = self.user["role"] in ("Departmental", "Administrative")
                if not (is_requester or is_head):
                    return "Deny", "Not the recipient", fields
 
            # Rule 8: no failure above
            return "Permit", "Signature, access and recipient verified", fields
 
        except Exception as error:               # any fault defaults to Deny
            return "Deny", f"Error: {error}", fields
 
    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------
    def show_result(self, decision, color, reason):
        """Update the big result label and clear/refill the details box."""
        self.result_label.configure(text=decision, text_color=color)
        self.details.delete("0.0", "end")
        if reason:
            self.details.insert("0.0", f"Reason: {reason}\n\n")
 
    def set_state(self, request_id, new_state):
        """Update the request's state (e.g. 'Delivered')."""
        self.cursor.execute("UPDATE Requests SET state = %s WHERE request_id = %s",
                            (new_state, request_id))
 
    def mark_qr_claimed(self, request_id):
        """NEW: mark the request's Active QR as Claimed so it can't be reused."""
        self.cursor.execute(
            "UPDATE QrCodes SET status = 'Claimed' "
            "WHERE request_id = %s AND status = 'Active'", (request_id,))
 
    def log_decision(self, decision, reason, fields):
        """Append every decision to the audit log."""
        fields = fields or {}
        self.cursor.execute(
            "INSERT INTO AuditLog (timestamp, employee_id, request_id, sku_id, "
            "compartment_id, decision, reason) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (datetime.now(), self.user["id"], fields.get("request_id"),
             fields.get("sku_id"), fields.get("compartment_id"), decision, reason))
 
 
# ---------------------------------------------------------------------------
# Test helper: run `python package_receive.py` to make a sample QR image
# you can hold up to the camera. NOTE: this sample is NOT in the QrCodes table,
# so scanning it will now be denied. Generate real QRs from the Inventory
# Terminal instead.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import qrcode
 
    sample = {"request_id": 1, "sku_id": "SUP-GLV-BX", "quantity": 28,
              "compartment_id": "C-02", "description": "Surgical Gloves (Box)",
              "destination": "ICU", "sensitivity": "Routine"}
    sample["tag"] = sign_fields(sample)
    qrcode.make(json.dumps(sample)).save("sample_qr.png")
    print("Saved sample_qr.png")
 