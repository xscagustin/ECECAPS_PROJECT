import datetime
import ssl

if not hasattr(ssl, "PROTOCOL_TLSv1"):
    ssl.PROTOCOL_TLSv1 = ssl.PROTOCOL_TLS
if not hasattr(ssl, "PROTOCOL_TLSv1_1"):
    ssl.PROTOCOL_TLSv1_1 = ssl.PROTOCOL_TLS
if not hasattr(ssl, "PROTOCOL_TLSv1_2"):
    ssl.PROTOCOL_TLSv1_2 = ssl.PROTOCOL_TLS

import mysql.connector

cnx = mysql.connector.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="1212")

cursor = cnx.cursor()

cursor.execute("USE {}".format('employees'))

query = ("SELECT first_name, last_name, hire_date FROM employees "
         "WHERE hire_date BETWEEN %s AND %s")

hire_start = datetime.date(2010, 1, 1)
hire_end = datetime.date(2015, 12, 31)

cursor.execute(query, (hire_start, hire_end))

for (first_name, last_name, hire_date) in cursor:
  print("{}, {} was hired on {:%d %b %Y}".format(
    last_name, first_name, hire_date))

cursor.close()
cnx.close()