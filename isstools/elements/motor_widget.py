from PyQt5 import uic, QtGui, QtCore
import pkg_resources

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_motor_widget.ui')


class UIMotorWidget(*uic.loadUiType(ui_path)):

    def __init__(self, motor_dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        # motor_dict = {'name' : BLA, 'object' : BLA}

        self.label_name.setText(motor_dict['name'])

        self.motor = motor_dict['object']
        self.motor.user_readback.subscribe(self.update_user_readback)


    def update_user_readback(self):
        x = self.motor.user_readback.get()
        self.lineEdit_user_readback.setText(str(x))