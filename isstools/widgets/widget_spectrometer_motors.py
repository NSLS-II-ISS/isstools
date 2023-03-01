import pkg_resources
from PyQt5 import uic, QtWidgets
from PyQt5.QtCore import QThread, QSettings
from PyQt5.Qt import  QObject
from bluesky.callbacks import LivePlot
from bluesky.callbacks.mpl_plotting import LiveScatter
import bluesky.plan_stubs as bps
import bluesky.plans as bp
import numpy as np
from functools import partial
from PyQt5.QtWidgets import QLabel, QPushButton, QLineEdit

from isstools.dialogs import MoveMotorDialog
from isstools.dialogs.BasicDialogs import question_message_box
from isstools.elements.figure_update import update_figure_with_colorbar, update_figure, setup_figure
from isstools.elements.transformations import  range_step_2_start_stop_nsteps
from isstools.widgets import widget_johann_tools
from xas.spectrometer import analyze_elastic_scan
from ..elements.liveplots import XASPlot, NormPlot#, XASPlotX
from ..elements.elements import get_spectrometer_line_dict
# from isstools.elements.liveplots import NormPlot
from isstools.widgets import widget_emission_energy_selector
ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_spectrometer_motors_tab.ui')

class UISpectrometerMotors(*uic.loadUiType(ui_path)):
    def __init__(self,
                 RE,
                 # plan_processor,
                 # hhm,
                 db,
                 # johann_emission,
                 # detector_dictionary,
                 motor_dictionary,
                 # shutter_dictionary,
                 # aux_plan_funcs,
                 # ic_amplifiers,
                 # service_plan_funcs,
                 # tune_elements,
                 # shutter_dictionary,
                 parent=None,
                 *args, **kwargs
                 ):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.RE = RE
        self.db = db
        self.parent = parent
        self.motor_dictonary = motor_dictionary

        self._det_arm_parent = self.motor_dictonary['johann_det_focus']['object'].parent
        self._det_arm_motors = ['motor_det_x', 'motor_det_th1', 'motor_det_th2']
        self._det_arm_dict = {}

        for i, motor in enumerate(self._det_arm_motors):
            __motor = getattr(self._det_arm_parent, motor)

            self._det_arm_dict[motor] = {}

            self.gridLayout_hrs_goinometer.addWidget(QLabel(motor), i, 0)


            self._det_arm_dict[motor][motor + "_mov_status"] = QLabel("      ")
            self._det_arm_dict[motor][motor + "_mov_status"].setStyleSheet('background-color: rgb(95,249,95)')
            self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "_mov_status"], i, 1)

            self._det_arm_dict[motor][motor + "set_point"] =  QLineEdit()
            _user_setpoint = f"{__motor.user_setpoint.get():3.3f}"
            self._det_arm_dict[motor][motor + "set_point"].setText(_user_setpoint)
            self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "set_point"], i, 2)

            self._det_arm_dict[motor][motor + "llim_status"] = QLabel("      ")
            self._det_arm_dict[motor][motor + "llim_status"].setStyleSheet('background-color: rgb(95,249,95)')
            self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "llim_status"], i, 3)


            self._det_arm_dict[motor][motor + "readback"] = QLineEdit()
            _user_readback = f"{__motor.user_readback.get():3.3f}"
            self._det_arm_dict[motor][motor + "readback"].setText(_user_readback)
            self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "readback"], i, 4)


            self._det_arm_dict[motor][motor + "hlim_status"] = QLabel("      ")
            self._det_arm_dict[motor][motor + "hlim_status"].setStyleSheet('background-color: rgb(95,249,95)')
            self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "hlim_status"], i, 5)

            self._det_arm_dict[motor][motor + "_dec"] = QPushButton()
            self._det_arm_dict[motor][motor + "_dec"].setText("<")
            self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + '_dec'], i, 6)
            self._det_arm_dict[motor][motor + "_dec"].clicked.connect(partial(self.update_motor_decrement, motor))

            self._det_arm_dict[motor][motor + "step"] = QLineEdit()
            if motor == 'motor_det_x':
                self._det_arm_dict[motor][motor + "step"].setText(str(1.00) + " mm")
                self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "step"], i, 7)
            else:
                self._det_arm_dict[motor][motor + "step"].setText(str(1.00) + " deg")
                self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "step"], i, 7)


            self._det_arm_dict[motor][motor + "_inc"] = QPushButton()
            self._det_arm_dict[motor][motor + "_inc"].setText(">")
            self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "_inc"], i, 8)


            self._det_arm_dict[motor][motor + "stop"] = QPushButton()
            self._det_arm_dict[motor][motor + "stop"].setText('Stop')
            self.gridLayout_hrs_goinometer.addWidget(self._det_arm_dict[motor][motor + "stop"], i, 9)


    def update_motor_decrement(self, motor_key):
        pass
        # _current_step = self._det_arm_dict[motor_key][motor_key + "step"].Text()
        # print(_current_step)



        _det_stage_parent = 0

