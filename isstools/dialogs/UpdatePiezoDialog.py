from PyQt4 import uic, QtGui, QtCore
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'dialogs/UpdatePiezoDialog.ui')

class UpdatePiezoDialog(*uic.loadUiType(ui_path)):

    def __init__(self, line, center, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Update Piezo Info')

        self.lineEdit.setText('{}'.format(line))
        self.lineEdit_2.setText('{}'.format(center))

    def getValues(self):
        return self.lineEdit.text(), self.lineEdit_2.text()
