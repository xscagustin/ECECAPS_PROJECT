from tkinter import *
from tkinter import ttk


root = Tk()
root.title("Table Test")
root.geometry("500x500")

my_tree = ttk.Treeview(root)

headers_request = ('item_name', 'quantity', 'date_time', 'courier_id', 'requester_id', 'state')
headers_inventory = ('item_name', 'sku_id','quantity', 'date_time', 'package_id')
data_inventory1 = ('Amoxicillin 500mg Capsules', 'MED-AMX-500', 67, '2026-10-27 09:23:37', 'PK0002')
data_request1 = ('Surgical Gloves (Box)', 28, '2026-10-08 07:05:42', 'C007', 'R033', 'On Hold')

#column definition
my_tree['columns'] = ('Name', 'ID', 'Favorite Pizza')


#format columns
my_tree.column("#0", width=0, stretch=NO)
for column in my_tree['columns']:
    my_tree.column(column, anchor=W, width=120)

# my_tree.column("#0", width=0, stretch=NO)
# my_tree.column('Name', anchor=W, width=120)
# my_tree.column('ID', anchor=W, width=80)
# my_tree.column('Favorite Pizza', anchor=W, width=120)

#headings

my_tree.heading('#0', text='', anchor=W)
for column in my_tree['columns']:
    my_tree.heading(column, text=column, anchor=W)

# my_tree.heading('#0', text='', anchor=W)
# my_tree.heading('Name', text='Name', anchor=W)
# my_tree.heading('ID', text='ID', anchor=W)
# my_tree.heading('Favorite Pizza', text='Favorite Pizza', anchor=W)

#insert data

my_tree.insert(parent='', index='end', text='Parent', values=('John', 1, 'Pepperoni'))
my_tree.insert(parent='', index='end', text='Parent', values=('Mary', 2, 'Cheese'))
my_tree.insert(parent='', index='end', text='Parent', values=('Kirk', 3, 'Mushroom'))

my_tree.pack(pady=20)

                                                                     

root.mainloop()