import ssl

if not hasattr(ssl, "PROTOCOL_TLSv1"):
    ssl.PROTOCOL_TLSv1 = ssl.PROTOCOL_TLS
if not hasattr(ssl, "PROTOCOL_TLSv1_1"):
    ssl.PROTOCOL_TLSv1_1 = ssl.PROTOCOL_TLS
if not hasattr(ssl, "PROTOCOL_TLSv1_2"):
    ssl.PROTOCOL_TLSv1_2 = ssl.PROTOCOL_TLS

from tkinter import *
from tkinter import ttk
import customtkinter as ctk
import mysql.connector

cnx = mysql.connector.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="1212")

cursor = cnx.cursor()
database = 'HospitalDatabase'

headers_request = ('item_name', 'quantity', 'date_time', 'courier_id', 'requester_id', 'state')
headers_inventory = ('item_name', 'sku_id','quantity', 'date_time', 'package_id')
data_inventory1 = ('Amoxicillin 500mg Capsules', 'MED-AMX-500', 67, '2026-10-27,' '09:23:37', 'PK0002')
data_request1 = ('Surgical Gloves (Box)', 28, '2026-10-08', '07:05:42', 'C007', 'R033', 'On Hold')



class RequestsTable(ctk.CTkFrame):
    def __init__(self, master, data):
        super().__init__(master)
    
        self.data = data
        self.page = 0
        header_sizes = (200, 60, 100, 100, 100, 100, 150)
        header_titles = ('Item Name', 'Quantity', 'Date', 'Time', 'Courier ID', 'Requester ID', 'State')

        #table
        self.tree = ttk.Treeview(self)
        self.tree['columns'] = ('item_name', 'quantity', 'date', 'time', 'courier_id', 'requester_id', 'state')
        
        #column and column header setup
        self.tree.column('#0', width=0, stretch=NO)
        self.tree.heading('#0', text='', anchor=W)
        for idx, column in enumerate(self.tree['columns']):
            self.tree.column(column, anchor=W, width=header_sizes[idx])
            self.tree.heading(column, text=header_titles[idx], anchor=W)

        #page number
        self.pagebox = ctk.CTkTextbox(master=self, width=60, corner_radius=0)
        self.pagebox.pack(pady=50)
        self.pagebox.insert("0.0", f"Page: {self.page+1}")

        #filter
        self.filter = ctk.CTkComboBox(self, width=140, )
        self.filter.pack(pady=20)

        #display first page
        query = (f"SELECT * from Requests LIMIT 10")
        cursor.execute(query)
        for data in cursor:
            self.tree.insert(parent='', index='end', text='', values=data)

        #button next
        self.button1 = ctk.CTkButton(master=self,text='Next Page',command=self.next_page)
        self.button1.pack(pady=12,padx=10)

        #butten prev
        self.button2 = ctk.CTkButton(master=self,text='Prev Page',command=self.prev_page)
        self.button2.pack(pady=12,padx=10)

        
        self.tree.pack(pady=20)
        self.pack(pady=20)


    def filter(self):
         pass

    def next_page(self):

        if self.page < 9:
            self.page+=1
    
            self.tree.delete(*self.tree.get_children())
            query = (f"SELECT * from Requests "
                    f"LIMIT 10 "
                    f"OFFSET {10*self.page}")
            cursor.execute(query)
            for data in cursor:
                    self.tree.insert(parent='', index='end', text='', values=data)
            self.pagebox.delete("0.0", 'end')
            self.pagebox.insert("0.0", f"Page: {self.page+1}")

    def prev_page(self):

        if self.page > 0:
            self.page-=1
            
            self.tree.delete(*self.tree.get_children())
            query = (f"SELECT * from Requests "
                    f"LIMIT 10 "
                    f"OFFSET {10*self.page}")
            cursor.execute(query)
            for data in cursor:
                    self.tree.insert(parent='', index='end', text='', values=data)
            self.pagebox.delete("0.0", 'end')
            self.pagebox.insert("0.0", f"Page: {self.page+1}")

    
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("500x500")
        self.title("Test Table")

        cursor.execute(f"USE {database}")
        
        self.label = ctk.CTkLabel(self, text='Test for Table')
        self.label.pack(pady=20)

        self.table = RequestsTable(self, data_request1)


if __name__ == "__main__":
    app = App()
    app.mainloop()
