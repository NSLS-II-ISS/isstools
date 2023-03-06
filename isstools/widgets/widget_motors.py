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
from isstools.widgets import widget_emission_energy_selector


ui_path = pkg_resources.resource_filename('isstools', 'ui/ui_motor_widget.ui')

class UIWidgetMotors(*uic.loadUiType(ui_path)):
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

        motor ='huber_stage_y'

        self.__motor = self.motor_dictonary[motor]['object']

        self.motor_label = QLabel("")

        self.motor_label.setText(motor)
        self.motor_layout.addWidget(self.motor_label, 0, 0)

        self.motor_mov_status = QLabel("      ")
        self.motor_mov_status.setStyleSheet('background-color: rgb(55,130,60)')
        self.motor_layout.addWidget(self.motor_mov_status, 1, 0)

        self.motor_set_point = QLineEdit("")
        _user_setpoint = f"{self.__motor.user_setpoint.get():3.3f} mm"
        self.motor_set_point.setText(_user_setpoint)
        self.motor_layout.addWidget(self.motor_set_point, 2, 0)

        self.motor_low_limit = QLabel("      ")
        self.motor_low_limit.setStyleSheet('background-color: rgb(94,20,20)')
        self.motor_layout.addWidget(self.motor_low_limit, 3, 0)

        self.motor_readback = QLineEdit("")
        self.motor_readback.setReadOnly(True)
        _user_readback = f"{self.__motor.user_readback.get():3.3f} mm"
        self.motor_readback.setText(_user_readback)
        self.motor_layout.addWidget(self.motor_readback, 4, 0)

        self.motor_high_limit = QLabel("      ")
        self.motor_high_limit.setStyleSheet('background-color: rgb(94,20,20)')
        self.motor_layout.addWidget(self.motor_high_limit, 5, 0)

        self.motor_decrement = QPushButton("<")
        self.motor_layout.addWidget(self.motor_decrement, 6, 0)

        self.motor_step = QLineEdit("")
        self.motor_step.setText(str(1.00) + " mm")
        self.motor_layout.addWidget(self.motor_step, 7, 0)

        self.motor_increment = QPushButton(">")
        self.motor_layout.addWidget(self.motor_increment, 8, 0)

        self.motor_stop = QPushButton("Stop")
        self.motor_layout.addWidget(self.motor_stop, 9, 0)



