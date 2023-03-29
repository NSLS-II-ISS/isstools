import pkg_resources
from PyQt5 import uic, QtCore
from PyQt5.QtGui import QPixmap
from isstools.elements.widget_motors import UIWidgetMotors
from functools import partial

ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_pilatus.ui')
spectrometer_image1 = pkg_resources.resource_filename('isstools', 'Resources/spec_image1.png')
spectrometer_image2 = pkg_resources.resource_filename('isstools', 'Resources/spec_image2.png')

class UIPilatusMonitor(*uic.loadUiType(ui_path)):
    def __init__(self,
                detector_dict = None,
                parent=None,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.parent = parent
        self.detector_dict = detector_dict

        self.pilatus100k_dict = self.detector_dict['Pilatus 100k']
        self.pilatus100k_device = self.detector_dict['Pilatus 100k']['device']

        self.subscription_dict = {'exposure': self.pilatus100k_device.cam.acquire_time,
                                  'num_of_images': self.pilatus100k_device.cam.num_images,
                                  'set_energy' : self.pilatus100k_device.cam.threshold_energy,
                                  'cutoff_energy': self.pilatus100k_device.cam.threshold_energy}

        self.gain_menu = {0: "7-30keV/Fast/LowG",
                          1: "5-18keV/Med/MedG",
                          2: "3-6keV/Slow/HighG",
                          3: "2-5keV/Slow/UltraG"}
        for i in range(4):
            self.comboBox_shapetime.addItem(self.gain_menu[i])

        self.comboBox_shapetime.currentIndexChanged.connect(self.change_pilatus_gain)
        self.pilatus100k_device.cam.gain_menu.subscribe(self.update_gain_combobox)



        for _keys in self.subscription_dict.keys():
            self.add_pilatus_attribute(_keys)

    def add_pilatus_attribute(self, attribute_key):

        def update_item(_attr_key, _attr_signal):
            _current_value = getattr(self, "doubleSpinBox_"+_attr_key).value()
            _st = _attr_signal.set(_current_value)

        def update_item_value(value ,**kwargs):
            if attribute_key == "exposure":
                unit = 's'
            elif attribute_key == 'num_of_images':
                unit = " "
            else:
                unit = "keV"
            getattr(self, "label_"+attribute_key).setText(f"{value:2.3f} {unit}")

        getattr(self, "doubleSpinBox_"+attribute_key).valueChanged.connect(partial(update_item, attribute_key, self.subscription_dict[attribute_key]))
        self.subscription_dict[attribute_key].subscribe(update_item_value)

    def change_pilatus_gain(self):
        _current_indx = self.comboBox_shapetime.currentIndex()
        _st = self.pilatus100k_device.cam.gain_menu.set(_current_indx)

    def update_gain_combobox(self, value, **kwargs):
        self.comboBox_shapetime.setCurrentIndex(value)






        # if key == 'exposure':
        #     getattr(self, 'label_' + key).setText(f"{value:1.3f} s")
        # elif key == 'num_of_images':
        #     getattr(self, 'label_' + key).setText(f"{value:1.0f}")
        # else:
        #     getattr(self, 'label_' + key).setText(f"{value:2.3f} keV")
        # self.label_exposure.setText(f"{value:1.2f} s")





        # self.motor_dict=motor_dict
        # pixmap = QPixmap(spectrometer_image1)
        # pixmap = pixmap.scaled(1000, 700, QtCore.Qt.KeepAspectRatio)
        # self.label_spectrometer_image_1.setPixmap(pixmap)
        #
        # pixmap = QPixmap(spectrometer_image2)
        # pixmap = pixmap.scaled(900, 400, QtCore.Qt.KeepAspectRatio)
        # self.label_spectrometer_image_2.setPixmap(pixmap)
        # self.widget_list=[]

    #     self._motor_group_dict = {
    #         'pushButton_detector_arm':  ['motor_det_x', 'motor_det_th1', 'motor_det_th2'],
    #         'pushButton_crystal_assembly': ['auxxy_x', 'auxxy_y'],
    #         'pushButton_stack1': ['johann_cr_main_roll', 'johann_cr_main_yaw'],
    #         'pushButton_stack2': ['johann_cr_aux2_roll', 'johann_cr_aux2_yaw', 'johann_cr_aux2_x', 'johann_cr_aux2_y'],
    #         'pushButton_stack3': ['johann_cr_aux3_roll', 'johann_cr_aux3_yaw', 'johann_cr_aux3_x', 'johann_cr_aux3_y'],
    #         'pushButton_stack4': [],
    #         'pushButton_stack5': [],
    #         }
    #     for button in self._motor_group_dict.keys():
    #         getattr(self,button).clicked.connect(self.show_motors)
    #
    # def show_motors(self):
    #     sender_object_name = self.sender().objectName()
    #     for widget in self.widget_list:
    #         self.verticalLayout_currentMotors.removeWidget(widget)
    #         widget.deleteLater()
    #     self.widget_list=[]
    #
    #     for motor in self._motor_group_dict[sender_object_name]:
    #         widget = UIWidgetMotors(self.motor_dict[motor])
    #         widget.setFixedWidth(900)
    #         widget.setFixedHeight(24)
    #         self.verticalLayout_currentMotors.addWidget(widget)
    #         self.widget_list.append(widget)


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
