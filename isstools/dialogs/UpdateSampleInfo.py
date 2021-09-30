from PyQt5 import uic, QtGui, QtCore
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'dialogs/UpdateSampleInfo.ui')

class UpdateSampleInfo(*uic.loadUiType(ui_path)):

    def __init__(self, name, comment, x, y, theta, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowTitle('Update Sample Info')
        self.lineEdit_name.setText(name)
        self.lineEdit_comment.setText(comment)
        self.doubleSpinBox_x.setValue(x)
        self.doubleSpinBox_y.setValue(y)
        self.doubleSpinBox_theta.setValue(theta)

    def getValues(self):
        return self.lineEdit_name.text(), self.lineEdit_comment.text(), \
               self.doubleSpinBox_x.value(), self.doubleSpinBox_y.value(), self.doubleSpinBox_theta.value()
