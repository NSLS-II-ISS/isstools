from PyQt5 import  QtWidgets

def message_box(title, message):
    messageBox = QtWidgets.QMessageBox()
    messageBox.setText(message)
    messageBox.addButton(QtWidgets.QPushButton('OK'), QtWidgets.QMessageBox.YesRole)
    messageBox.setWindowTitle(title)
    messageBox.exec_()
