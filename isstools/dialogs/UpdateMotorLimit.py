from PyQt5 import uic, QtGui, QtCore
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'dialogs/UpdateMotorLimits.ui')

class UIUpdateMotorLimit(*uic.loadUiType(ui_path)):
    def __init__(self, motor_object, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self._motor_object = motor_object
        # self._motor_object.