from tkinter import *
from tkinter import ttk
import customtkinter as ctk

headers_request = ('item_name', 'quantity', 'date_time', 'courier_id', 'requester_id', 'state')
headers_inventory = ('item_name', 'sku_id','quantity', 'date_time', 'package_id')
data_inventory1 = ('Amoxicillin 500mg Capsules', 'MED-AMX-500', 67, '2026-10-27,' '09:23:37', 'PK0002')
data_request1 = ('Surgical Gloves (Box)', 28, '2026-10-08', '07:05:42', 'C007', 'R033', 'On Hold')




class RequestsTable(ctk.CTkFrame):
    def __init__(self, master, data):
        super().__init__(master)
    
        self.data = data
        header_size = (200, 60, 100, 100, 100, 100, 150)

        #table
        self.tree = ttk.Treeview(self)
        self.tree['columns'] = ('item_name', 'quantity', 'date', 'time', 'courier_id', 'requester_id', 'state')
        

        #column setup
        self.tree.column('#0', width=0, stretch=NO)
        self.tree.column(self.tree['columns'][0], anchor=W, width=200)
        self.tree.column(self.tree['columns'][1], anchor=W, width=60)
        self.tree.column(self.tree['columns'][2], anchor=W, width=100)
        self.tree.column(self.tree['columns'][3], anchor=W, width=100)
        self.tree.column(self.tree['columns'][4], anchor=W, width=100)
        self.tree.column(self.tree['columns'][5], anchor=W, width=100)
        self.tree.column(self.tree['columns'][6], anchor=W, width=150)
       

        #header setup
        self.tree.heading('#0', text='', anchor=W)
        self.tree.heading(self.tree['columns'][0], text='Item Name', anchor=W)
        self.tree.heading(self.tree['columns'][1], text='Quantity', anchor=W)
        self.tree.heading(self.tree['columns'][2], text='Date', anchor=W)
        self.tree.heading(self.tree['columns'][3], text='Time', anchor=W)
        self.tree.heading(self.tree['columns'][4], text='Courier ID', anchor=W)
        self.tree.heading(self.tree['columns'][5], text='Requester ID', anchor=W)
        self.tree.heading(self.tree['columns'][6], text='State', anchor=W)
    
        #button
        self.button = ctk.CTkButton(master=self,text='Given data',command=self.insert_data)
        self.button.pack(pady=12,padx=10)

        
        self.tree.pack(pady=20)
        self.pack(pady=20)

    def insert_data(self):
        print('button pressed')
        self.tree.insert(parent='', index='end', text='Parent', values=self.data)

    

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("500x500")
        self.title("Test Table")
        
        self.label = ctk.CTkLabel(self, text='Test for Table')
        self.label.pack(pady=20)

        self.table = RequestsTable(self, data_request1)





if __name__ == "__main__":
    app = App()
    app.mainloop()
