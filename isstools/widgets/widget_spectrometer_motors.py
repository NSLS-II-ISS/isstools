import pkg_resources
from PyQt5 import uic, QtWidgets, QtGui, QtCore
from PyQt5.QtGui import QPixmap
from isstools.widgets.widget_motors import UIWidgetMotors


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_spectrometer_motors_tab.ui')
spectrometer_image1 = pkg_resources.resource_filename('isstools', 'Resources/spec_image1.png')
spectrometer_image2 = pkg_resources.resource_filename('isstools', 'Resources/spec_image2.png')



class UISpectrometerMotors(*uic.loadUiType(ui_path)):
    def __init__(self,
                 RE,
                 db,
                              motor_dictionary,
                parent=None,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.RE = RE
        self.db = db
        self.parent = parent
        self.motor_dictonary = motor_dictionary

        pixmap = QPixmap(spectrometer_image1)
        pixmap = pixmap.scaled(1000, 700, QtCore.Qt.KeepAspectRatio)
        self.label_spectrometer_image_1.setPixmap(pixmap)


        pixmap = QPixmap(spectrometer_image2)
        pixmap = pixmap.scaled(900, 400, QtCore.Qt.KeepAspectRatio)
        self.label_spectrometer_image_2.setPixmap(pixmap)
        # self.label_spectrometer_image_2.resize(pixmap.width(), pixmap.height())

        self._det_arm_parent = self.motor_dictonary['johann_det_focus']['object'].parent
        self._det_arm_motors = ['motor_det_x', 'motor_det_th1', 'motor_det_th2']
        self._det_arm_dict = {}

        self._huber_motors = ['huber_stage_y', 'huber_stage_z']
        self._huber_dict = {}

    #     self.pushButton_stack1.clicked.connect(self.launch_stack1_motors)
    #
    # def launch_stack1_motors(self):
    #     self.layout_motors = QtWidgets.verticalLayout()
    #     pass

        # self.verticalLayout_detector_arm.addWidget(UIWidgetMotors(self.motor_dictonary['huber_stage_y']))
        # for motor in self._huber_motors:
        #     self.verticalLayout_det_stage.addWidget(UIWidgetMotors(self.motor_dictonary[motor],
        #                                                            self.parent))



        # self._motor = UIWidgetMotors(self.RE, self.db, self.motor_dictonary, self._huber_motors[0], self.parent)
        # self.gridLayout_test.addWidget(self._motor)


    #     for i, motor in enumerate(self._det_arm_motors):
    #         __motor = getattr(self._det_arm_parent, motor)
    #
    #         self._det_arm_dict[motor] = {}
    #
    #         self.gridLayout_hrs_goinometer.addWidget(QLabel(motor), i, 0)
    #
    #
    #         self._det_arm_dict[motor][motor + "_mov_status"] = QLabel("      ")
    #         self._det_arm_dict[motor][motor + "_mov_status"].setStyleSheet('background-color: rgb(95,249,95)')
    #         self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "_mov_status"], i, 1)
    #
    #         self._det_arm_dict[motor][motor + "set_point"] =  QLineEdit()
    #         _user_setpoint = f"{__motor.user_setpoint.get():3.3f}"
    #         self._det_arm_dict[motor][motor + "set_point"].setText(_user_setpoint)
    #         self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "set_point"], i, 2)
    #
    #         self._det_arm_dict[motor][motor + "llim_status"] = QLabel("      ")
    #         self._det_arm_dict[motor][motor + "llim_status"].setStyleSheet('background-color: rgb(95,249,95)')
    #         self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "llim_status"], i, 3)
    #
    #
    #         self._det_arm_dict[motor][motor + "readback"] = QLineEdit()
    #         _user_readback = f"{__motor.user_readback.get():3.3f}"
    #         self._det_arm_dict[motor][motor + "readback"].setText(_user_readback)
    #         self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "readback"], i, 4)
    #
    #
    #         self._det_arm_dict[motor][motor + "hlim_status"] = QLabel("      ")
    #         self._det_arm_dict[motor][motor + "hlim_status"].setStyleSheet('background-color: rgb(95,249,95)')
    #         self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "hlim_status"], i, 5)
    #
    #         self._det_arm_dict[motor][motor + "_dec"] = QPushButton()
    #         self._det_arm_dict[motor][motor + "_dec"].setText("<")
    #         self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + '_dec'], i, 6)
    #         self._det_arm_dict[motor][motor + "_dec"].clicked.connect(partial(self.update_motor_decrement, motor))
    #
    #         self._det_arm_dict[motor][motor + "step"] = QLineEdit()
    #         if motor == 'motor_det_x':
    #             self._det_arm_dict[motor][motor + "step"].setText(str(1.00) + " mm")
    #             self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "step"], i, 7)
    #         else:
    #             self._det_arm_dict[motor][motor + "step"].setText(str(1.00) + " deg")
    #             self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "step"], i, 7)
    #
    #
    #         self._det_arm_dict[motor][motor + "_inc"] = QPushButton()
    #         self._det_arm_dict[motor][motor + "_inc"].setText(">")
    #         self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "_inc"], i, 8)
    #
    #
    #         self._det_arm_dict[motor][motor + "stop"] = QPushButton()
    #         self._det_arm_dict[motor][motor + "stop"].setText('Stop')
    #         self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "stop"], i, 9)
    #
    #     for i, motor in enumerate(self._huber_motors):
    #         __motor = self.motor_dictonary[motor]['object']
    #
    #
    #
    #         self._huber_dict[motor] = {}
    #
    #         self.gridLayout_det_stage1.addWidget(QLabel(motor), i, 0)
    #
    #         self._huber_dict[motor][motor + "_mov_status"] = QLabel("      ")
    #         self._huber_dict[motor][motor + "_mov_status"].setStyleSheet('background-color: rgb(55,130,60)')
    #         self.gridLayout_det_stage1.addWidget(self._huber_dict[motor][motor + "_mov_status"], i, 1)
    #
    #         self._huber_dict[motor][motor + "_set_point"] = QLineEdit()
    #         _user_setpoint = f"{__motor.user_setpoint.get():3.3f} mm"
    #         self._huber_dict[motor][motor + "_set_point"].setText(_user_setpoint)
    #         self.gridLayout_det_stage1.addWidget(self._huber_dict[motor][motor + "_set_point"], i, 2)
    #         self._huber_dict[motor][motor + "_set_point"].returnPressed.connect(partial(self.update_set_point, motor))
    #
    #         self._huber_dict[motor][motor + "_llim_status"] = QLabel("      ")
    #         self._huber_dict[motor][motor + "_llim_status"].setStyleSheet('background-color: rgb(95,249,95)')
    #         self.gridLayout_det_stage1.addWidget(self._huber_dict[motor][motor + "_llim_status"], i, 3)
    #
    #         self._huber_dict[motor][motor + "_readback"] = QLineEdit()
    #         self._huber_dict[motor][motor + "_readback"].setReadOnly(True)
    #         _user_readback = f"{__motor.user_readback.get():3.3f} mm"
    #         self._huber_dict[motor][motor + "_readback"].setText(_user_readback)
    #         self.gridLayout_det_stage1.addWidget(self._huber_dict[motor][motor + "_readback"], i, 4)
    #         __motor.user_readback.subscribe(self.update_readback)
    #
    #         self._huber_dict[motor][motor + "_hlim_status"] = QLabel("      ")
    #         self._huber_dict[motor][motor + "_hlim_status"].setStyleSheet('background-color: rgb(95,249,95)')
    #         self.gridLayout_det_stage1.addWidget(self._huber_dict[motor][motor + "_hlim_status"], i, 5)
    #
    #         self._huber_dict[motor][motor + "_dec"] = QPushButton()
    #         self._huber_dict[motor][motor + "_dec"].setText("<")
    #         self.gridLayout_det_stage1.addWidget(self._huber_dict[motor][motor + '_dec'], i, 6)
    #         self._huber_dict[motor][motor + "_dec"].clicked.connect(partial(self.update_motor_decrement, motor))
    #
    #         self._huber_dict[motor][motor + "_step"] = QLineEdit()
    #         self._huber_dict[motor][motor + "_step"].setText(str(1.00) + " mm")
    #         self.gridLayout_det_stage1.addWidget(self._huber_dict[motor][motor + "_step"], i, 7)
    #         self._huber_dict[motor][motor + "_step"].returnPressed.connect(partial(self.update_step, motor))
    #
    #
    #         self._huber_dict[motor][motor + "_inc"] = QPushButton()
    #         self._huber_dict[motor][motor + "_inc"].setText(">")
    #         self.gridLayout_det_stage1.addWidget(self._huber_dict[motor][motor + "_inc"], i, 8)
    #         self._huber_dict[motor][motor + "_inc"].clicked.connect(partial(self.update_motor_increment, motor))
    #
    #         self._huber_dict[motor][motor + "_stop"] = QPushButton()
    #         self._huber_dict[motor][motor + "_stop"].setText('Stop')
    #         self.gridLayout_det_stage1.addWidget(self._huber_dict[motor][motor + "_stop"], i, 9)
    #         self._huber_dict[motor][motor + "_dec"].clicked.connect(partial(self.stop_motor, motor))
    #
    # def update_motor_decrement(self, motor_key):
    #     current_step_reading = self._huber_dict[motor_key][motor_key + '_step'].text()
    #     step = float(current_step_reading.split()[0])
    #
    #     current_readback_reading = float(self.motor_dictonary[motor_key]['object'].get().user_readback)
    #     self._huber_dict[motor_key][motor_key + "_set_point"].setText(f"{current_readback_reading - step:3.3f} mm")
    #
    #     obj = self.motor_dictonary[motor_key]['object'].set(current_readback_reading - step, wait=False)
    #     while obj.done != True:
    #         self._huber_dict[motor_key][motor_key + "_mov_status"].setStyleSheet('background-color: rgb(95,249,95)')
    #     self._huber_dict[motor_key][motor_key + "_mov_status"].setStyleSheet('background-color: rgb(55,130,60)')
    #     _user_readback = f"{self.motor_dictonary[motor_key]['object'].user_readback.get():3.3f} mm"
    #     self._huber_dict[motor_key][motor_key + "_readback"].setText(_user_readback)
    #
    # def update_motor_increment(self, motor_key):
    #     current_step_reading = self._huber_dict[motor_key][motor_key + '_step'].text()
    #     step = float(current_step_reading.split()[0])
    #
    #     current_readback_reading = float(self.motor_dictonary[motor_key]['object'].get().user_readback)
    #     self._huber_dict[motor_key][motor_key + "_set_point"].setText(f"{current_readback_reading + step:3.3f} mm")
    #
    #     obj = self.motor_dictonary[motor_key]['object'].set(current_readback_reading + step, wait=False)
    #     while obj.done != True:
    #         self._huber_dict[motor_key][motor_key + "_mov_status"].setStyleSheet('background-color: rgb(95,249,95)')
    #     self._huber_dict[motor_key][motor_key + "_mov_status"].setStyleSheet('background-color: rgb(55,130,60)')
    #     _user_readback = f"{self.motor_dictonary[motor_key]['object'].user_readback.get():3.3f} mm"
    #     print(_user_readback)
    #     self._huber_dict[motor_key][motor_key + "_readback"].setText(_user_readback)
    #
    # def update_set_point(self, motor_key):
    #     _read_desired_setpoint = self._huber_dict[motor_key][motor_key + "_set_point"].text()
    #     _desired_setpoint = float(_read_desired_setpoint.split()[0])
    #     self.motor_dictonary[motor_key]['object'].set(_desired_setpoint)
    #     _setpoint_text = f"{_desired_setpoint:3.3f} mm"
    #     self._huber_dict[motor_key][motor_key + "_set_point"].setText(_setpoint_text)
    #
    # def update_step(self, motor_key):
    #     _read_desired_step = self._huber_dict[motor_key][motor_key + "_step"].text()
    #     _desired_step = float(_read_desired_step.split()[0])
    #     _step_text = f"{_desired_step:3.3f} mm"
    #     self._huber_dict[motor_key][motor_key + "_step"].setText(_step_text)
    #
    # def update_readback(self, value, old_value):
    #     print(f"{value = }, {old_value = }")
    #
    # def stop_motor(self, motor_key):
    #     self.motor_dictonary[motor_key]['object'].stop()





# ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_motor_widget.ui')
# class UIMotorWidget(*uic.loadUiType('/nsls2/data/iss/shared/config/repos/isstools/isstools/ui/ui_motor_widget.ui')):
#     def __init__(self,
#                  motor_dict=None,
#                  parent=None,
#                  *args, **kwargs
#                  ):
#         super().__init__(*args, **kwargs)
#         self.setupUi(self)
#
#
#
# motor_widget = UIMotorWidget()
# motor_widget.show()