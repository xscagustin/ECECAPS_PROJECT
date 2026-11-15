from __future__ import print_function
import ssl

if not hasattr(ssl, "PROTOCOL_TLSv1"):
    ssl.PROTOCOL_TLSv1 = ssl.PROTOCOL_TLS
if not hasattr(ssl, "PROTOCOL_TLSv1_1"):
    ssl.PROTOCOL_TLSv1_1 = ssl.PROTOCOL_TLS
if not hasattr(ssl, "PROTOCOL_TLSv1_2"):
    ssl.PROTOCOL_TLSv1_2 = ssl.PROTOCOL_TLS

from datetime import date, datetime, timedelta
import mysql.connector



cnx = mysql.connector.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="1212")

cursor = cnx.cursor()

cursor.execute("USE {}".format('employees'))

tomorrow = datetime.now().date() + timedelta(days=1)

add_employee = ("INSERT INTO employees "
               "(first_name, last_name, hire_date, gender, birth_date) "
               "VALUES (%s, %s, %s, %s, %s)")
add_salary = ("INSERT INTO salaries "
              "(emp_no, salary, from_date, to_date) "
              "VALUES (%(emp_no)s, %(salary)s, %(from_date)s, %(to_date)s)")

data_employees = [
    ('John', 'Rodriguez', date(2015, 1, 3), 'M', date(1975, 12, 27)),
    ('Michael', 'Moore', date(2023, 3, 31), 'M', date(1968, 11, 25)),
    ('Sarah', 'Smith', date(2014, 11, 27), 'F', date(1969, 3, 16)),
    ('Marcus', 'Martin', date(2022, 8, 3), 'M', date(1966, 3, 11)),
    ('Marcus', 'Wilson', date(2020, 1, 28), 'M', date(1974, 11, 21)),
    ('Sarah', 'Garcia', date(2019, 6, 25), 'F', date(1996, 4, 26)),
    ('Isabella', 'Jones', date(2017, 7, 20), 'F', date(1974, 8, 29)),
    ('Michael', 'Gonzalez', date(2018, 1, 19), 'M', date(1969, 5, 4)),
    ('Chloe', 'Rodriguez', date(2010, 12, 22), 'F', date(2001, 3, 16)),
    ('Elena', 'Brown', date(2011, 10, 8), 'F', date(1981, 12, 24)),
]

# Insert new employee
for data_employee in data_employees:
    cursor.execute(add_employee, data_employee)
emp_no = cursor.lastrowid

# Insert salary information
data_salary = {
  'emp_no': emp_no,
  'salary': 50000,
  'from_date': tomorrow,
  'to_date': date(9999, 1, 1),
}
cursor.execute(add_salary, data_salary)

# Make sure data is committed to the database
cnx.commit()

cursor.close()
cnx.close()