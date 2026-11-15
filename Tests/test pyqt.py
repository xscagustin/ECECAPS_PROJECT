import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QTableView,
)


header_titles = ('Item Name', 'Quantity', 'Date', 'Time', 'Courier ID', 'Requester ID', 'State')

class Contacts(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QTableView Example")
        self.resize(415, 200)
        # Set up the model
        self.model = QSqlTableModel(self)
        self.model.setTable("contacts")
        self.model.setEditStrategy(QSqlTableModel.OnFieldChange)
        self.model.setHeaderData(0, Qt.Horizontal, "Item Name")
        self.model.setHeaderData(1, Qt.Horizontal, "Quantity")
        self.model.setHeaderData(2, Qt.Horizontal, "Date")
        self.model.setHeaderData(3, Qt.Horizontal, "Time")
        self.model.setHeaderData(3, Qt.Horizontal, "Courier ID")
        self.model.setHeaderData(3, Qt.Horizontal, "Requester ID")
        self.model.setHeaderData(3, Qt.Horizontal, "State")
        self.model.select()
        # Set up the view
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.resizeColumnsToContents()
        self.setCentralWidget(self.view)

def createConnection():
    con = QSqlDatabase.addDatabase("QMYSQL")
    con.setDatabaseName("HospitalDatabase")
    if not con.open():
        QMessageBox.critical(
            None,
            "QTableView Example - Error!",
            "Database Error: %s" % con.lastError().databaseText(),
        )
        return False
    return True


app = QApplication(sys.argv)
if not createConnection():
    sys.exit(1)
win = Contacts()
win.show()
sys.exit(app.exec_())