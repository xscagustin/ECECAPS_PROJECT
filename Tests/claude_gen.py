"""
One-time helper: creates HospitalDatabase, widens the columns so IDs like
'MS-18' and 'PKG-1048' fit, and inserts sample rows (only if the tables are empty).
Safe to run more than once.

Run:  python setup_database.py
"""

import ssl

# Same compatibility shim as the app (not needed after upgrading mysql-connector-python)
if not hasattr(ssl, "PROTOCOL_TLSv1"):
    ssl.PROTOCOL_TLSv1 = ssl.PROTOCOL_TLS
if not hasattr(ssl, "PROTOCOL_TLSv1_1"):
    ssl.PROTOCOL_TLSv1_1 = ssl.PROTOCOL_TLS
if not hasattr(ssl, "PROTOCOL_TLSv1_2"):
    ssl.PROTOCOL_TLSv1_2 = ssl.PROTOCOL_TLS

import mysql.connector

CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "1212",
    "connection_timeout": 5,
}

INVENTORY = [
    # item_name, sku_id, quantity, package_id
    ("Insulin vials",       "INS-204", 24, "PKG-1048"),
    ("Emergency kit",       "EMR-101",  2, "PKG-1046"),
    ("Sterile packs",       "STP-305", 12, "PKG-1049"),
    ("Syringe packs",       "SPR-118", 48, "PKG-1047"),
    ("Lab reagent",         "LBR-402",  6, "PKG-1045"),
    ("Diagnostic supplies", "DIA-209", 18, "PKG-1044"),
]

REQUESTS = [
    # item_name, quantity, minutes_ago, courier_id, requester_id, state
    ("Surgical consumables", 36, 40, "CE-03", "MS-09", "Held"),
    ("Document pouch",        1, 34, "CE-03", "MS-09", "Ready"),
    ("Diagnostic supplies",  18, 28, "CE-05", "MS-11", "Ready"),
    ("Lab reagent",           6, 22, "CE-05", "MS-11", "Held"),
    ("Syringe packs",        48, 17, "CE-09", "MS-22", "Held"),
    ("Sterile packs",        12, 11, "CE-09", "MS-22", "Ready"),
    ("Emergency kit",         2,  8, "CE-12", "MS-18", "Ready"),
    ("Insulin vials",        24, 14, "CE-12", "MS-18", "Ready"),
]


def main():
    conn = mysql.connector.connect(**CONFIG)
    cur = conn.cursor()

    cur.execute("CREATE DATABASE IF NOT EXISTS HospitalDatabase")
    cur.execute("USE HospitalDatabase")

    cur.execute("""CREATE TABLE IF NOT EXISTS Inventory(
        item_name VARCHAR(50), sku_id VARCHAR(12), quantity INT,
        date_time DATETIME, package_id VARCHAR(12))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS Requests(
        item_name VARCHAR(50), quantity INT, date_time DATETIME,
        courier_id VARCHAR(10), requester_id VARCHAR(10), state VARCHAR(10))""")

    # Widen columns on tables that were created with the original sizes
    cur.execute("ALTER TABLE Inventory MODIFY package_id VARCHAR(12)")
    cur.execute("ALTER TABLE Requests MODIFY courier_id VARCHAR(10), "
                "MODIFY requester_id VARCHAR(10)")

    cur.execute("SELECT COUNT(*) FROM Inventory")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO Inventory (item_name, sku_id, quantity, date_time, package_id) "
            "VALUES (%s, %s, %s, NOW(), %s)", INVENTORY)
        print(f"Inserted {len(INVENTORY)} inventory rows")
    else:
        print("Inventory already has data - left unchanged")

    cur.execute("SELECT COUNT(*) FROM Requests")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO Requests (item_name, quantity, date_time, courier_id, "
            "requester_id, state) VALUES (%s, %s, NOW() - INTERVAL %s MINUTE, %s, %s, %s)",
            [(n, q, m, c, r, s) for n, q, m, c, r, s in REQUESTS])
        print(f"Inserted {len(REQUESTS)} request rows")
    else:
        print("Requests already has data - left unchanged")

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()