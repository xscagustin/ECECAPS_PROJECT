import datetime
import ssl

if not hasattr(ssl, "PROTOCOL_TLSv1"):
    ssl.PROTOCOL_TLSv1 = ssl.PROTOCOL_TLS
if not hasattr(ssl, "PROTOCOL_TLSv1_1"):
    ssl.PROTOCOL_TLSv1_1 = ssl.PROTOCOL_TLS
if not hasattr(ssl, "PROTOCOL_TLSv1_2"):
    ssl.PROTOCOL_TLSv1_2 = ssl.PROTOCOL_TLS

import mysql.connector
import customtkinter as ctk

cnx = mysql.connector.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="1212")

cursor = cnx.cursor()

database = "HospitalDatabase"
cursor.execute(f"USE {database}")

class SQLTableViewer(ctk.Frame):
    def __init__(self, master):
        super().__init__()
        self.grid_columnfigure(0, weight=1)

        table_values = ['Requests', 'Inventory']
        table_drop = ctk.CTkComboBox(master=self, values=table_values)

        filter_values = ['item_name', 'quantity', 'date_time', 'courier_id', 'requeste_id', 'state']
        filter_drop = ctk.CTkComboBox(master=self, values=table_values)

        condition_values = ['item_name', 'quantity', 'date_time', 'courier_id', 'requeste_id', 'state']
        condition = ctk.CTkComboBox(master=self, values=table_values)

    def retrieve_table():
        query = (f"SELECT * from {table} "
             f"WHERE {filter} = '{filter_condition}'")
    
        cursor.execute(query)
        column_heads = [column[0] for column in cursor.description]

        for head in column_heads:
            print(f"{head} | ",end="")


        for column in cursor:
            for i in range(len(column)):
                print(f"{column[i]} | ",end="")
            print("\n")        



class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Hospital App")
        self.geometry("400x200")


app = App()
app.mainloop()

