import pkg_resources
from PyQt5 import uic, QtCore
from PyQt5.QtGui import QPixmap
from isstools.elements.widget_motors import UIWidgetMotors

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_spectrometer_motors.ui')


class UISpectrometerMotors(*uic.loadUiType(ui_path)):
    def __init__(self,
                detector = None,
                parent=None,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.motor_dict=motor_dict
        self.widget_list=[]


        for button in self._motor_group_dict.keys():
            getattr(self,button).clicked.connect(self.show_motors)

    def show_motors(self):
        sender_object_name = self.sender().objectName()
        for widget in self.widget_list:
            self.verticalLayout_currentMotors.removeWidget(widget)
            widget.deleteLater()
        self.widget_list=[]

        for motor in self._motor_group_dict[sender_object_name]:
            widget = UIWidgetMotors(self.motor_dict[motor])
            widget.setFixedWidth(900)
            widget.setFixedHeight(24)
            self.verticalLayout_currentMotors.addWidget(widget)
            self.widget_list.append(widget)


    #
    #
    # def launch_stack_motors_widget(self, stack_number=1):
    #     _stack_motors = {1: ['johann_cr_main_roll', 'johann_cr_main_yaw'],
    #                      2: ['johann_cr_aux2_roll', 'johann_cr_aux2_yaw', 'johann_cr_aux2_x', 'johann_cr_aux2_y'],
    #                      3: ['johann_cr_aux3_roll', 'johann_cr_aux3_yaw', 'johann_cr_aux3_x', 'johann_cr_aux3_y']}
    #
    #
    #     self.widget_stack_motors.setWindowTitle(f"Stack {stack_number} Motors")
    #     self.layout_stack = QtWidgets.QVBoxLayout(self.widget_stack_motors)
    #
    #
    #     for motor_name in _stack_motors[stack_number]:
    #         widget = UIWidgetMotors(self.motor_dictonary[motor_name])
    #         widget.setFixedWidth(800)
    #         self.layout_stack.addWidget(widget)
    #     self.widget_stack_motors.show()
    #     # self.motor_list.append(self.widget_stack_motors)
    #
    # def launch_det_arm_motor_widget(self):
    #     _det_arm_motors = ['motor_det_x', 'motor_det_th1', 'motor_det_th2']
    #
    #     self.widget_det_motors = QtWidgets.QWidget()
    #     self.widget_det_motors.setGeometry(1100, 1100, 900, 140)
    #     self.widget_det_motors.setWindowTitle(f"Detector arm Motors")
    #     self.layout_det = QtWidgets.QVBoxLayout(self.widget_det_motors)
    #
    #
    #     for motor_name in _det_arm_motors:
    #         widget = UIWidgetMotors(self.motor_dictonary[motor_name])
    #         widget.setFixedWidth(800)
    #         self.layout_det.addWidget(widget)
    #     self.motor_list.append(self.widget_det_motors)
    #     self.widget_det_motors.show()
    #
    #
    # def launch_cry_assy_widget(self):
    #     _cry_assy_motors = ['auxxy_x', 'auxxy_y']
    #     # ['johann_bragg_angle', 'johann_energy']
    #
    #     self.widget_cry_assy_motors = QtWidgets.QWidget()
    #     self.widget_cry_assy_motors.setGeometry(1200, 1200, 900, 140)
    #     self.widget_cry_assy_motors.setWindowTitle(f"Detector arm Motors")
    #     self.layout_cry_assy = QtWidgets.QVBoxLayout(self.widget_cry_assy_motors)
    #
    #     for motor_name in _cry_assy_motors:
    #         widget = UIWidgetMotors(self.motor_dictonary[motor_name])
    #         widget.setFixedWidth(800)
    #         self.layout_cry_assy.addWidget(widget)
    #
    #     self.motor_list.append(self.widget_cry_assy_motors)
    #     self.widget_cry_assy_motors.show()
    #
    #
