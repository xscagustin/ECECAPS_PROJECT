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



#terminal UI to provide base commands for 
table = "Inventory" #input("What table to view? (Inventory/Requests)")
#command = input("Pick between these: Display All | Filter: ")
filter = "item_name" #input("Filter by? :")
filter_condition = "IV Catheter 20G" #input("What condition?")
#access = input("What is your access level? ")

database = "HospitalDatabase"
cursor.execute(f"USE {database}")

# display all

def display_table(table, filter, filter_condition):
    

    query = (f"SELECT * from {table} "
             f"WHERE {filter} = '{filter_condition}'")
    
    cursor.execute(query)
    column_heads = [column[0] for column in cursor.description]

    for head in column_heads:
        print(f"{head} | ",end="")

    print('\n')

    for column in cursor:
        for i in range(len(column)):
            print(f"{column[i]} | ",end="")
        print("\n")

    



display_table(table, filter, filter_condition)


# display by filter

# add to database


cursor.close()
cnx.close()