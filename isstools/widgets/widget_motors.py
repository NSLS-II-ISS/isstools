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
        self.motor_dictionary = motor_dictionary
        #
        motor ='huber_stage_y'

        self.__motor = self.motor_dictionary[motor]['object']

        self.motor_label = QLabel("")

        self.motor_layout = self.horizontalLayout_motor
        self.motor_label.setText(motor)
        self.motor_layout.addWidget(self.motor_label)

        self.motor_mov_status = QLabel("      ")
        self.motor_mov_status.setStyleSheet('background-color: rgb(55,130,60)')
        self.motor_layout.addWidget(self.motor_mov_status)

        self.motor_set_point = QLineEdit("")
        _user_setpoint = f"{self.__motor.user_setpoint.get():3.3f} mm"
        self.motor_set_point.setText(_user_setpoint)
        self.motor_layout.addWidget(self.motor_set_point)
        self.motor_set_point.returnPressed.connect(self.update_set_point)

        self.motor_low_limit = QLabel("      ")
        self.motor_low_limit.setStyleSheet('background-color: rgb(94,20,20)')
        self.motor_layout.addWidget(self.motor_low_limit)
        _current_high_limit = self.__motor.high_limit
        _current_low_limit = self.__motor.low_limit
        if _current_low_limit == 0.0 and _current_high_limit == 0.0:
            pass
        elif self.__motor.user_readback.get()-1 <= _current_low_limit:
            self.motor_low_limit.setStyleSheet('background-color: rgb(255,0,0)')
        self.motor_layout.addWidget(self.motor_low_limit)

        self.motor_readback = QLineEdit("")
        self.motor_readback.setReadOnly(True)
        _user_readback = f"{self.__motor.user_readback.get():3.3f} mm"
        self.motor_readback.setText(_user_readback)
        self.__motor.user_readback.subscribe(self.update_readback)
        self.motor_layout.addWidget(self.motor_readback)

        self.motor_high_limit = QLabel("      ")
        self.motor_high_limit.setStyleSheet('background-color: rgb(94,20,20)')
        _current_high_limit = self.__motor.high_limit
        _current_low_limit = self.__motor.low_limit
        if _current_low_limit == 0.0 and _current_high_limit == 0.0:
            pass
        elif self.__motor.user_readback.get()+1 >= _current_high_limit:
            self.motor_high_limit.setStyleSheet('background-color: rgb(255,0,0)')
        self.motor_layout.addWidget(self.motor_high_limit)

        self.motor_decrement = QPushButton("<")
        self.motor_layout.addWidget(self.motor_decrement)
        self.motor_decrement.clicked.connect(self.update_decrement)

        self.motor_step = QLineEdit("")
        self.motor_step.setText(str(1.00) + " mm")
        self.motor_layout.addWidget(self.motor_step)
        self.motor_step.returnPressed.connect(self.update_step)

        self.motor_increment = QPushButton(">")
        self.motor_layout.addWidget(self.motor_increment)
        self.motor_increment.clicked.connect(self.update_increment)

        self.motor_stop = QPushButton("Stop")
        self.motor_layout.addWidget(self.motor_stop)
        self.motor_stop.clicked.connect(self.stop_the_motor)


    def update_readback(self):
        _current_readback = self.__motor.user_readback.get()
        self.motor_readback.setText(f"{_current_readback:3.3f} mm")


    def update_step(self):
        _user_step_reading = self.motor_step.text()
        _step_convert = float(_user_step_reading.split()[0])
        _step_text = f"{_step_convert:3.3f} mm"
        self.motor_step.setText(_step_text)

    def update_decrement(self):
        _current_step_reading = self.motor_step.text()
        _step = float(_current_step_reading.split()[0])

        _current_readback = self.__motor.user_readback.get()
        _set_obj = self.__motor.set(_current_readback - _step)
        while not _set_obj.done:
            self.motor_mov_status.setStyleSheet('background-color: rgb(95,249,95)')
        self.motor_mov_status.setStyleSheet('background-color: rgb(55,130,60)')
        _current_readback = self.__motor.user_readback.get()
        self.motor_set_point.setText(f"{_current_readback:3.3f} mm")
        self.motor_readback.setText(f"{_current_readback:3.3f} mm")

        _current_high_limit = self.__motor.high_limit
        _current_low_limit = self.__motor.low_limit
        if _current_low_limit == 0.0 and _current_high_limit == 0.0:
            pass
        if self.__motor.user_readback.get()-1 <= _current_low_limit:
            self.motor_low_limit.setStyleSheet('background-color: rgb(255,0,0)')
        else:
            self.motor_low_limit.setStyleSheet('background-color: rgb(94,20,20)')
        if self.__motor.user_readback.get()+1 >= _current_high_limit:
            self.motor_high_limit.setStyleSheet('background-color: rgb(255,0,0)')
        else:
            self.motor_high_limit.setStyleSheet('background-color: rgb(94,20,20)')

    def update_increment(self):
        _current_step_reading = self.motor_step.text()
        _step = float(_current_step_reading.split()[0])

        _current_readback = self.__motor.user_readback.get()
        _set_obj = self.__motor.set(_current_readback + _step)
        while not _set_obj.done:
            self.motor_mov_status.setStyleSheet('background-color: rgb(95,249,95)')
        self.motor_mov_status.setStyleSheet('background-color: rgb(55,130,60)')
        _current_readback = self.__motor.user_readback.get()
        self.motor_set_point.setText(f"{_current_readback:3.3f} mm")
        self.motor_readback.setText(f"{_current_readback:3.3f} mm")

        _current_high_limit = self.__motor.high_limit
        _current_low_limit = self.__motor.low_limit
        if _current_low_limit == 0.0 and _current_high_limit == 0.0:
            pass
        if self.__motor.user_readback.get()-1 <= _current_low_limit:
            self.motor_low_limit.setStyleSheet('background-color: rgb(255,0,0)')
        else:
            self.motor_low_limit.setStyleSheet('background-color: rgb(94,20,20)')
        if self.__motor.user_readback.get()+1 >= _current_high_limit:
            self.motor_high_limit.setStyleSheet('background-color: rgb(255,0,0)')
        else:
            self.motor_high_limit.setStyleSheet('background-color: rgb(94,20,20)')



    def update_set_point(self):
        _read_desired_setpoint = self.motor_set_point.text()
        _desired_setpoint = float(_read_desired_setpoint.split()[0])
        _set_obj = self.__motor.set(_desired_setpoint)
        while not _set_obj.done:
            self.motor_mov_status.setStyleSheet('background-color: rgb(95,249,95)')
        self.motor_mov_status.setStyleSheet('background-color: rgb(55,130,60)')
        _current_readback = self.__motor.user_readback.get()
        self.motor_set_point.setText(f"{_current_readback:3.3f} mm")
        self.motor_readback.setText(f"{_current_readback:3.3f} mm")

        _current_high_limit = self.__motor.high_limit
        _current_low_limit = self.__motor.low_limit
        if _current_low_limit == 0.0 and _current_high_limit == 0.0:
            pass
        if self.__motor.user_readback.get()-1 <= _current_low_limit:
            self.motor_low_limit.setStyleSheet('background-color: rgb(255,0,0)')
        else:
            self.motor_low_limit.setStyleSheet('background-color: rgb(94,20,20)')
        if self.__motor.user_readback.get()+1 >= _current_high_limit:
            self.motor_high_limit.setStyleSheet('background-color: rgb(255,0,0)')
        else:
            self.motor_high_limit.setStyleSheet('background-color: rgb(94,20,20)')

    def stop_the_motor(self):
        self.__motor.stop()
